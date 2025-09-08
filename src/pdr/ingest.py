"""Ingest Codex CLI logs into SQLite."""

from __future__ import annotations

import glob
import json
import os
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from json import JSONDecodeError

from rapidfuzz import fuzz

from .db import create_schema, fts_insert
from .util import canonicalize, redact, sha256_text

# Near-duplicate detection thresholds
NEAR_DUP_SCORE = 90
NEAR_DUP_LEN_DELTA = 0.15


def _parse_json_lines(path: str) -> Iterable[tuple[dict, str]]:
    """Yield (obj, raw_line) from JSON/JSONL file, tolerant to stray lines."""

    def _parse_line(line: str) -> tuple[dict, str]:
        try:
            return json.loads(line), line
        except JSONDecodeError:
            return {"text": line, "role": "user"}, line

    with open(path, encoding="utf-8", errors="ignore") as fh:
        if path.endswith(".jsonl"):
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue
                yield _parse_line(line)
            return

        try:
            data = json.load(fh)
        except JSONDecodeError:
            fh.seek(0)
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue
                yield _parse_line(line)
            return

        # Normalize: allow array or object with messages
        if isinstance(data, list):
            for obj in data:
                yield obj, json.dumps(obj)
        elif isinstance(data, dict) and "messages" in data:
            for obj in data["messages"]:
                yield obj, json.dumps(obj)
        else:
            yield data, json.dumps(data)


def _norm_ts(ts: str | None) -> str | None:
    if not ts:
        return None
    try:
        # Accept isoformat or epoch string
        if ts.isdigit():
            dt = datetime.fromtimestamp(int(ts), tz=UTC)
        else:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def ingest_paths(
    conn,
    paths: list[str],
    date: str | None = None,
    since_days: int | None = None,
) -> int:
    """Ingest all JSON/JSONL under given glob paths.

    Args:
        conn: SQLite connection.
        paths: List of glob patterns.
        date: ISO date filter (YYYY-MM-DD). Keep rows whose message ts matches that day,
          or fallback to file mtime if ts missing.
        since_days: If provided, include files modified in the last N days.

    Returns:
        Count of inserted rows.
    """
    create_schema(conn)
    seen = set(h for (h,) in conn.execute("SELECT canonical_hash FROM prompt_raw"))

    def in_date(file_path: str, msg_ts: str | None) -> bool:
        if date:
            if msg_ts:
                return msg_ts.startswith(date)
            # fallback to file mtime
            mtime = datetime.fromtimestamp(os.path.getmtime(file_path), tz=UTC).date().isoformat()
            return mtime == date
        if since_days:
            cutoff = datetime.now(tz=UTC) - timedelta(days=since_days)
            when = datetime.fromtimestamp(os.path.getmtime(file_path), tz=UTC)
            return when >= cutoff
        return True

    inserted = 0
    recent_canonicals: list[str] = []

    def _handle_record(file_path: str, obj: dict, raw: str) -> None:
        nonlocal inserted
        text = str(obj.get("text") or obj.get("content") or "")
        role = obj.get("role") or "user"
        session_id = obj.get("session_id") or obj.get("session") or None
        conversation_id = obj.get("conversation_id") or obj.get("conversation") or None
        ts = _norm_ts(obj.get("ts") or obj.get("timestamp"))
        if not in_date(file_path, ts):
            return

        safe_text = redact(text)
        canon = canonicalize(safe_text)
        h = sha256_text(canon)
        if h in seen:
            return

        # Near-dup gate
        for prior in recent_canonicals[-200:]:
            score = fuzz.partial_ratio(canon, prior)
            if score >= NEAR_DUP_SCORE:
                delta = abs(len(canon) - len(prior)) / max(1, len(prior))
                if delta <= NEAR_DUP_LEN_DELTA:
                    return

        cur = conn.execute(
            (
                "\n".join(
                    [
                        "INSERT INTO prompt_raw(",
                        "  source_path, session_id, conversation_id,",
                        "  role, ts, text, canonical_hash, raw_json",
                        ")",
                        "VALUES (?,?,?,?,?,?,?,?)",
                    ]
                )
            ),
            (
                file_path,
                session_id,
                conversation_id,
                role,
                ts,
                safe_text,
                h,
                raw,
            ),
        )
        rowid = int(cur.lastrowid)
        fts_insert(conn, "prompt_raw_fts", rowid, safe_text)
        inserted += 1
        seen.add(h)
        recent_canonicals.append(canon)

    for pattern in paths:
        for file_path in glob.glob(os.path.expanduser(pattern), recursive=True):
            if not (file_path.endswith(".json") or file_path.endswith(".jsonl")):
                continue
            for obj, raw in _parse_json_lines(file_path):
                _handle_record(file_path, obj, raw)

    conn.commit()
    return inserted

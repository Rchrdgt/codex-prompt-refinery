"""Hybrid search: FTS union vector with simple scoring."""

from __future__ import annotations

import sqlite3

from .config import embeddings_client, get_settings
from .db import vec_knn
from .util import json_dumps


def _embed_query(text: str) -> str | None:
    """Return query embedding JSON string or None on failure."""
    try:
        settings = get_settings()
        client = embeddings_client(settings)
        resp = client.embeddings.create(
            model=settings.embedding_model, input=[text], dimensions=settings.embedding_dimensions
        )
        return json_dumps(resp.data[0].embedding)
    except Exception:
        return None


def _build_predicate_raw(filters: dict | None) -> tuple[str, list]:
    where: list[str] = []
    params: list = []
    if not filters:
        return "", []
    w = filters.get("where") or {}
    ts = w.get("ts") or {}
    if ts.get("from"):
        where.append("pr.ts >= ?")
        params.append(ts.get("from"))
    if ts.get("to"):
        where.append("pr.ts <= ?")
        params.append(ts.get("to"))
    roles = w.get("roles") or []
    if roles:
        where.append("pr.role IN (" + ",".join(["?"] * len(roles)) + ")")
        params.extend(list(roles))
    sessions = w.get("sessions") or []
    if sessions:
        where.append("pr.session_id IN (" + ",".join(["?"] * len(sessions)) + ")")
        params.extend(list(sessions))
    if where:
        return " AND " + " AND ".join(where), params
    return "", []


def _build_predicate_opt(filters: dict | None) -> tuple[str, list]:
    where: list[str] = []
    params: list = []
    if not filters:
        return "", []
    w = filters.get("where") or {}
    ts = w.get("ts") or {}
    if ts.get("from"):
        where.append("po.created_at >= ?")
        params.append(ts.get("from"))
    if ts.get("to"):
        where.append("po.created_at <= ?")
        params.append(ts.get("to"))
    kinds = w.get("kind") or []
    if kinds:
        where.append("po.kind IN (" + ",".join(["?"] * len(kinds)) + ")")
        params.extend(list(kinds))
    if where:
        return " AND " + " AND ".join(where), params
    return "", []


def hybrid_search(
    conn, query: str, topn_fts: int = 20, topk_vec: int = 20, filters: dict | None = None
) -> dict[str, list[dict]]:
    """Run hybrid search across raw and optimized prompts.

    Args:
        conn: SQLite connection.
        query: Query text.
        topn_fts: FTS limit.
        topk_vec: Vector limit.
        filters: Optional filter JSON (v1) dict with 'where' keys like ts/roles/sessions/kind.

    Returns:
        Dict with 'raw' and 'optimized' results lists.
    """
    results_raw: list[dict] = []
    results_opt: list[dict] = []

    # FTS with graceful LIKE fallback when FTS5 is unavailable, with JOIN to apply predicates
    def _fts_or_like_raw() -> list[dict]:
        out: list[dict] = []
        pred_sql, pred_params = _build_predicate_raw(filters)
        try:
            sql = (
                "SELECT pr.id AS id, pr.text AS text, 1.0 AS score "
                "FROM prompt_raw_fts fr JOIN prompt_raw pr ON pr.id = fr.rowid "
                "WHERE fr MATCH ?" + pred_sql + " LIMIT ?"
            )
            rows = conn.execute(sql, (query, *pred_params, topn_fts)).fetchall()
        except sqlite3.OperationalError:
            sql = (
                "SELECT pr.id AS id, pr.text AS text, 1.0 AS score "
                "FROM prompt_raw pr WHERE pr.text LIKE ? ESCAPE '\\'" + pred_sql + " LIMIT ?"
            )
            rows = conn.execute(sql, (f"%{query}%", *pred_params, topn_fts)).fetchall()
        for r in rows:
            out.append({"id": int(r["id"]), "text": r["text"], "score": 1.0})
        return out

    def _fts_or_like_opt() -> list[dict]:
        out: list[dict] = []
        pred_sql, pred_params = _build_predicate_opt(filters)
        try:
            sql = (
                "SELECT po.id AS id, po.text_md AS text, 1.0 AS score "
                "FROM prompt_opt_fts fo JOIN prompt_optimized po ON po.id = fo.rowid "
                "WHERE fo MATCH ?" + pred_sql + " LIMIT ?"
            )
            rows = conn.execute(sql, (query, *pred_params, topn_fts)).fetchall()
        except sqlite3.OperationalError:
            sql = (
                "SELECT po.id AS id, po.text_md AS text, 1.0 AS score "
                "FROM prompt_optimized po WHERE po.text_md LIKE ? ESCAPE '\\'"
                + pred_sql
                + " LIMIT ?"
            )
            rows = conn.execute(sql, (f"%{query}%", *pred_params, topn_fts)).fetchall()
        for r in rows:
            out.append({"id": int(r["id"]), "text": r["text"], "score": 1.0})
        return out

    results_raw.extend(_fts_or_like_raw())
    results_opt.extend(_fts_or_like_opt())

    # Vector
    qvec = _embed_query(query)
    if qvec and topk_vec > 0:
        # Vector + post-filter by predicates
        pred_raw_sql, pred_raw_params = _build_predicate_raw(filters)
        pred_opt_sql, pred_opt_params = _build_predicate_opt(filters)

        for item_id, dist in vec_knn(conn, qvec, "raw", k=topk_vec):
            ok = True
            if pred_raw_sql:
                chk = conn.execute(
                    "SELECT 1 FROM prompt_raw pr WHERE pr.id=?" + pred_raw_sql + " LIMIT 1",
                    (int(item_id), *pred_raw_params),
                ).fetchone()
                ok = bool(chk)
            if ok:
                results_raw.append(
                    {
                        "id": int(item_id),
                        "text": _raw_text(conn, int(item_id)),
                        "score": 1.0 / (1.0 + dist),
                    }
                )

        for item_id, dist in vec_knn(conn, qvec, "optimized", k=topk_vec):
            ok = True
            if pred_opt_sql:
                chk = conn.execute(
                    "SELECT 1 FROM prompt_optimized po WHERE po.id=?" + pred_opt_sql + " LIMIT 1",
                    (int(item_id), *pred_opt_params),
                ).fetchone()
                ok = bool(chk)
            if ok:
                results_opt.append(
                    {
                        "id": int(item_id),
                        "text": _opt_text(conn, int(item_id)),
                        "score": 1.0 / (1.0 + dist),
                    }
                )

    def _dedupe(items: list[dict]) -> list[dict]:
        best: dict[int, dict] = {}
        for it in items:
            iid = int(it["id"])  # unify
            cur = best.get(iid)
            if (cur is None) or (it["score"] > cur["score"]):
                best[iid] = it
        out = list(best.values())
        out.sort(key=lambda x: (-x["score"], x["id"]))
        return out

    return {"raw": _dedupe(results_raw), "optimized": _dedupe(results_opt)}


def _raw_text(conn, rid: int) -> str:
    r = conn.execute("SELECT text FROM prompt_raw WHERE id=?", (rid,)).fetchone()
    return r["text"] if r else ""


def _opt_text(conn, oid: int) -> str:
    r = conn.execute("SELECT text_md FROM prompt_optimized WHERE id=?", (oid,)).fetchone()
    return r["text_md"] if r else ""

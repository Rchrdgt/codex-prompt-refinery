"""Synthesis via OpenAI Responses API with Structured Outputs."""

from __future__ import annotations

import datetime as _dt
import json as _json
import os

from openai import OpenAI

from .embed import embed_optimized_prompts
from .schemas import SynthesisOutput, schema_for_openai
from .util import json_dumps


def _client() -> OpenAI:
    return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def _cluster_payload(conn, member_ids: list[int]) -> dict:
    """Build cluster payload from raw prompts and nearby assistant replies."""
    msgs: list[tuple[str, str]] = []  # (role, text)
    for rid in member_ids[:10]:
        u = conn.execute(
            "SELECT id, text, ts, session_id FROM prompt_raw WHERE id=? AND role='user'", (rid,)
        ).fetchone()
        if not u:
            continue
        msgs.append(("user", u["text"]))
        # find next assistant in same session
        a = conn.execute(
            """
            SELECT text FROM prompt_raw
            WHERE role='assistant' AND session_id IS NOT NULL AND session_id=?
              AND id > ?
            ORDER BY id
            LIMIT 1
            """,
            (u["session_id"], u["id"]),
        ).fetchone()
        if a:
            msgs.append(("assistant", a["text"]))
    return {"examples": msgs}


def synthesize_for_clusters(conn, clusters: list[dict], model: str = "gpt-5-mini") -> int:
    """Call Responses API for each cluster, validate, and persist.

    Args:
        conn: SQLite connection.
        clusters: Cluster dicts from cluster.build_daily_clusters.
        model: OpenAI model id.

    Returns:
        Count of optimized prompts inserted.
    """
    if not clusters:
        return 0

    client = _client()
    inserted = 0
    schema = schema_for_openai()
    for c in clusters:
        payload = _cluster_payload(conn, c["members"])
        now = _dt.datetime.now().isoformat()
        # Build input: concise instruction + examples
        instruction = (
            "You are a senior prompt engineer. Given related user prompts and assistant snippets, "
            "synthesize reusable ATOMIC prompts and one WORKFLOW prompt. "
            "Output must adhere to the provided JSON Schema."
        )
        # Responses API with structured outputs
        resp = client.responses.create(  # pylint: disable=unexpected-keyword-arg
            model=model,
            instructions=instruction,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Related messages follow. Format and synthesize.",
                        },
                        {"type": "input_text", "text": json_dumps(payload)},
                    ],
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "pdr_synthesis", "schema": schema, "strict": True},
            },
        )
        # Extract parsed JSON (SDK exposes output_text; we decode to dict)
        data = (
            resp.output[0].content[0].get("json", None) if getattr(resp, "output", None) else None
        )
        if data is None:
            # Fallback: try text then parse
            data = _json.loads(resp.output_text)
        validated = SynthesisOutput.model_validate(data)

        # Persist optimized prompts
        # atomic
        for ap in validated.optimized_atomic_prompts:
            cur = conn.execute(
                (
                    "\n".join(
                        [
                            "INSERT INTO prompt_optimized(",
                            "  kind, title, text_md,",
                            "  variables_json, io_contract_json,",
                            "  rationale, created_at, cluster_hint, gpt_meta_json",
                            ")",
                            "VALUES (?,?,?,?,?,?,?,?,?)",
                        ]
                    )
                ),
                (
                    "atomic",
                    ap.title,
                    ap.prompt_markdown,
                    json_dumps([v.model_dump() for v in ap.variables]),
                    json_dumps(ap.io_contract.model_dump()),
                    validated.rationale,
                    now,
                    c.get("cluster_hint", ""),
                    json_dumps({"model": model}),
                ),
            )
            oid = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO prompt_opt_fts(rowid, text_md) VALUES (?,?)", (oid, ap.prompt_markdown)
            )
            # back-links
            for rid in ap.citations:
                conn.execute(
                    "INSERT OR IGNORE INTO prompt_link(optimized_id, raw_id) VALUES (?,?)",
                    (oid, int(rid)),
                )
            inserted += 1

        # workflow
        wp = validated.optimized_workflow_prompt
        cur = conn.execute(
            (
                "\n".join(
                    [
                        "INSERT INTO prompt_optimized(",
                        "  kind, title, text_md,",
                        "  variables_json, io_contract_json,",
                        "  rationale, created_at, cluster_hint, gpt_meta_json",
                        ")",
                        "VALUES (?,?,?,?,?,?,?,?,?)",
                    ]
                )
            ),
            (
                "workflow",
                wp.title,
                wp.prompt_markdown,
                json_dumps([v.model_dump() for v in wp.variables]),
                json_dumps(wp.io_contract.model_dump()),
                validated.rationale,
                now,
                c.get("cluster_hint", ""),
                json_dumps({"model": model}),
            ),
        )
        oid = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO prompt_opt_fts(rowid, text_md) VALUES (?,?)", (oid, wp.prompt_markdown)
        )
        for rid in wp.citations:
            conn.execute(
                "INSERT OR IGNORE INTO prompt_link(optimized_id, raw_id) VALUES (?,?)",
                (oid, int(rid)),
            )
        conn.commit()

    # Embed optimized prompts
    embed_optimized_prompts(conn)
    return inserted

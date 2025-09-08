"""Synthesis via OpenAI-compatible APIs with Structured Outputs."""

from __future__ import annotations

import datetime as _dt
import json as _json

from .config import default_llm_model, get_settings, llm_client
from .embed import embed_optimized_prompts
from .schemas import SynthesisOutput, schema_for_openai
from .util import json_dumps


def _cluster_payload(conn, member_ids: list[int]) -> dict:
    """Build cluster payload from raw prompts and nearby assistant replies."""
    msgs: list[tuple[str, str]] = []
    for rid in member_ids[:10]:
        u = conn.execute(
            "SELECT id, text, ts, session_id FROM prompt_raw WHERE id=? AND role='user'", (rid,)
        ).fetchone()
        if not u:
            continue
        msgs.append(("user", u["text"]))
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


def _openai_responses_call(client, model: str, instruction: str, payload: dict, schema: dict):
    """Call OpenAI Responses API with structured outputs."""
    resp = client.responses.create(
        model=model,
        instructions=instruction,
        input=[{"role": "user", "content": [{"type": "input_text", "text": json_dumps(payload)}]}],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "pdr_synthesis", "schema": schema, "strict": True},
        },
    )
    data = resp.output[0].content[0].get("json", None) if getattr(resp, "output", None) else None
    if data is None:
        data = _json.loads(resp.output_text)
    return data


def _cerebras_chat_call(client, model: str, instruction: str, payload: dict, schema: dict):
    """Call Cerebras OpenAI-compatible Chat Completions with JSON schema."""
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": json_dumps(payload)},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "pdr_synthesis", "schema": schema, "strict": True},
        },
    )
    text = completion.choices[0].message.content
    return _json.loads(text)


def synthesize_for_clusters(conn, clusters: list[dict], model: str | None = None) -> int:
    """Call LLM for each cluster, validate, and persist.

    Args:
        conn: SQLite connection.
        clusters: Cluster dicts from cluster.build_daily_clusters.
        model: Optional model override.

    Returns:
        Count of optimized prompts inserted.
    """
    if not clusters:
        return 0

    settings = get_settings()
    client = llm_client(settings)
    use_model = model or default_llm_model(settings)
    inserted = 0
    schema = schema_for_openai()
    instruction = (
        "You are a senior prompt engineer. Given related user prompts and assistant snippets, "
        "synthesize reusable ATOMIC prompts and one WORKFLOW prompt. "
        "Output MUST obey the provided JSON Schema."
    )

    for c in clusters:
        payload = _cluster_payload(conn, c["members"])
        now = _dt.datetime.now().isoformat()

        if settings.llm_provider == "cerebras":
            data = _cerebras_chat_call(client, use_model, instruction, payload, schema)
        else:
            data = _openai_responses_call(client, use_model, instruction, payload, schema)

        validated = SynthesisOutput.model_validate(data)

        # Persist optimized prompts
        for ap in validated.optimized_atomic_prompts:
            cur = conn.execute(
                """
                INSERT INTO prompt_optimized(kind, title, text_md, variables_json,
                    io_contract_json, rationale, created_at, cluster_hint, gpt_meta_json)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    "atomic",
                    ap.title,
                    ap.prompt_markdown,
                    json_dumps([v.model_dump() for v in ap.variables]),
                    json_dumps(ap.io_contract.model_dump()),
                    validated.rationale,
                    now,
                    c.get("cluster_hint", ""),
                    json_dumps({"model": use_model, "provider": settings.llm_provider}),
                ),
            )
            oid = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO prompt_opt_fts(rowid, text_md) VALUES (?,?)", (oid, ap.prompt_markdown)
            )
            for rid in ap.citations:
                conn.execute(
                    "INSERT OR IGNORE INTO prompt_link(optimized_id, raw_id) VALUES (?,?)",
                    (oid, int(rid)),
                )
            inserted += 1

        wp = validated.optimized_workflow_prompt
        cur = conn.execute(
            """
            INSERT INTO prompt_optimized(kind, title, text_md, variables_json,
                io_contract_json, rationale, created_at, cluster_hint, gpt_meta_json)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                "workflow",
                wp.title,
                wp.prompt_markdown,
                json_dumps([v.model_dump() for v in wp.variables]),
                json_dumps(wp.io_contract.model_dump()),
                validated.rationale,
                now,
                c.get("cluster_hint", ""),
                json_dumps({"model": use_model, "provider": settings.llm_provider}),
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

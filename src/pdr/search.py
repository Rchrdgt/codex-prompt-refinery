"""Hybrid search: FTS union vector with simple scoring."""

from __future__ import annotations

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


def hybrid_search(
    conn, query: str, topn_fts: int = 20, topk_vec: int = 20
) -> dict[str, list[dict]]:
    """Run hybrid search across raw and optimized prompts.

    Args:
        conn: SQLite connection.
        query: Query text.
        topn_fts: FTS limit.
        topk_vec: Vector limit.

    Returns:
        Dict with 'raw' and 'optimized' results lists.
    """
    results_raw: list[dict] = []
    results_opt: list[dict] = []

    # FTS
    for r in conn.execute(
        """
        SELECT rowid AS id, text, 1.0 AS score
        FROM prompt_raw_fts WHERE prompt_raw_fts MATCH ?
        LIMIT ?
        """,
        (query, topn_fts),
    ):
        results_raw.append({"id": int(r["id"]), "text": r["text"], "score": 1.0})

    for r in conn.execute(
        """
        SELECT rowid AS id, text_md AS text, 1.0 AS score
        FROM prompt_opt_fts WHERE prompt_opt_fts MATCH ?
        LIMIT ?
        """,
        (query, topn_fts),
    ):
        results_opt.append({"id": int(r["id"]), "text": r["text"], "score": 1.0})

    # Vector
    qvec = _embed_query(query)
    if qvec and topk_vec > 0:
        for item_id, dist in vec_knn(conn, qvec, "raw", k=topk_vec):
            results_raw.append(
                {"id": int(item_id), "text": _raw_text(conn, item_id), "score": 1.0 / (1.0 + dist)}
            )
        for item_id, dist in vec_knn(conn, qvec, "optimized", k=topk_vec):
            results_opt.append(
                {"id": int(item_id), "text": _opt_text(conn, item_id), "score": 1.0 / (1.0 + dist)}
            )

    results_raw.sort(key=lambda x: (-x["score"], x["id"]))
    results_opt.sort(key=lambda x: (-x["score"], x["id"]))
    return {"raw": results_raw, "optimized": results_opt}


def _raw_text(conn, rid: int) -> str:
    r = conn.execute("SELECT text FROM prompt_raw WHERE id=?", (rid,)).fetchone()
    return r["text"] if r else ""


def _opt_text(conn, oid: int) -> str:
    r = conn.execute("SELECT text_md FROM prompt_optimized WHERE id=?", (oid,)).fetchone()
    return r["text_md"] if r else ""

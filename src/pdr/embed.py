"""Embedding helpers via OpenAI API."""

from __future__ import annotations

import os

from openai import OpenAI

from .db import vec_insert
from .util import batched, json_dumps


def _client() -> OpenAI:
    return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def embed_new_user_prompts(
    conn, model: str = "text-embedding-3-small", dimensions: int | None = None, batch: int = 64
) -> int:
    """Embed user prompts that lack vectors.

    Args:
        conn: SQLite connection.
        model: Embedding model name.
        dimensions: Optional embedding dims override.
        batch: Batch size.

    Returns:
        Number of vectors inserted.
    """
    rows = conn.execute(
        """
        SELECT id, text FROM prompt_raw
        WHERE role='user'
          AND id NOT IN (SELECT item_id FROM embeddings WHERE kind='raw')
        ORDER BY id
        """
    ).fetchall()
    if not rows:
        return 0

    client = _client()
    inserted = 0
    ids = [int(r["id"]) for r in rows]
    texts = [r["text"] for r in rows]
    for b_ids, b_txts in zip(batched(ids, batch), batched(texts, batch), strict=False):
        resp = client.embeddings.create(
            model=model,
            input=list(b_txts),
            dimensions=dimensions,
        )
        for idx, emb in enumerate(resp.data):
            vec = json_dumps(emb.embedding)
            vec_insert(conn, vec, "raw", int(b_ids[idx]))
            inserted += 1
    conn.commit()
    return inserted


def embed_optimized_prompts(
    conn, model: str = "text-embedding-3-small", dimensions: int | None = None, batch: int = 64
) -> int:
    """Embed optimized prompts that lack vectors.

    Args:
        conn: SQLite connection.
        model: Embedding model name.
        dimensions: Optional embedding dims.
        batch: Batch size.

    Returns:
        Number of vectors inserted.
    """
    rows = conn.execute(
        """
        SELECT id, text_md FROM prompt_optimized
        WHERE id NOT IN (SELECT item_id FROM embeddings WHERE kind='optimized')
        ORDER BY id
        """
    ).fetchall()
    if not rows:
        return 0
    client = _client()
    inserted = 0
    ids = [int(r["id"]) for r in rows]
    texts = [r["text_md"] for r in rows]
    for b_ids, b_txts in zip(batched(ids, batch), batched(texts, batch), strict=False):
        resp = client.embeddings.create(
            model=model,
            input=list(b_txts),
            dimensions=dimensions,
        )
        for idx, emb in enumerate(resp.data):
            vec = json_dumps(emb.embedding)
            vec_insert(conn, vec, "optimized", int(b_ids[idx]))
            inserted += 1
    conn.commit()
    return inserted

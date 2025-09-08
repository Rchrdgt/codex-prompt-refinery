"""Embedding helpers via OpenAI API."""

from __future__ import annotations

from .config import embeddings_client, get_settings
from .db import vec_insert
from .util import batched, json_dumps


def embed_new_user_prompts(
    conn, model: str | None = None, dimensions: int | None = None, batch: int = 64
) -> int:
    """Embed user prompts that lack vectors.

    Args:
        conn: SQLite connection.
        model: Embedding model name override.
        dimensions: Optional dims override.
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

    settings = get_settings()
    client = embeddings_client(settings)
    use_model = model or settings.embedding_model
    dims = dimensions if dimensions is not None else settings.embedding_dimensions

    inserted = 0
    ids = [int(r["id"]) for r in rows]
    texts = [r["text"] for r in rows]
    for b_ids, b_txts in zip(batched(ids, batch), batched(texts, batch), strict=False):
        resp = client.embeddings.create(model=use_model, input=list(b_txts), dimensions=dims)
        for idx, emb in enumerate(resp.data):
            vec = json_dumps(emb.embedding)
            vec_insert(conn, vec, "raw", int(b_ids[idx]))
            inserted += 1
    conn.commit()
    return inserted


def embed_optimized_prompts(
    conn, model: str | None = None, dimensions: int | None = None, batch: int = 64
) -> int:
    """Embed optimized prompts that lack vectors.

    Args:
        conn: SQLite connection.
        model: Embedding model override.
        dimensions: Optional dims.
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

    settings = get_settings()
    client = embeddings_client(settings)
    use_model = model or settings.embedding_model
    dims = dimensions if dimensions is not None else settings.embedding_dimensions

    inserted = 0
    ids = [int(r["id"]) for r in rows]
    texts = [r["text_md"] for r in rows]
    for b_ids, b_txts in zip(batched(ids, batch), batched(texts, batch), strict=False):
        resp = client.embeddings.create(model=use_model, input=list(b_txts), dimensions=dims)
        for idx, emb in enumerate(resp.data):
            vec = json_dumps(emb.embedding)
            vec_insert(conn, vec, "optimized", int(b_ids[idx]))
            inserted += 1
    conn.commit()
    return inserted

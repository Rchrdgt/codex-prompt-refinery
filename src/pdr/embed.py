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
    # Filter out empty texts and clamp overly long inputs to reduce API errors
    max_chars = 12000
    pairs = [
        (int(r["id"]), (r["text"] or "").strip()[:max_chars])
        for r in rows
        if (r["text"] or "").strip()
    ]
    if not pairs:
        return 0

    for batch_pairs in batched(pairs, batch):
        b_ids = [pid for pid, _ in batch_pairs]
        b_txts = [txt for _, txt in batch_pairs]
        resp = client.embeddings.create(model=use_model, input=b_txts, dimensions=dims)
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
    max_chars = 12000
    pairs = [
        (int(r["id"]), (r["text_md"] or "").strip()[:max_chars])
        for r in rows
        if (r["text_md"] or "").strip()
    ]
    if not pairs:
        return 0

    for batch_pairs in batched(pairs, batch):
        b_ids = [pid for pid, _ in batch_pairs]
        b_txts = [txt for _, txt in batch_pairs]
        resp = client.embeddings.create(model=use_model, input=b_txts, dimensions=dims)
        for idx, emb in enumerate(resp.data):
            vec = json_dumps(emb.embedding)
            vec_insert(conn, vec, "optimized", int(b_ids[idx]))
            inserted += 1
    conn.commit()
    return inserted

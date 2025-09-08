"""Greedy daily clustering using vec KNN + cosine threshold."""

from __future__ import annotations

from .db import vec_knn
from .util import cosine_from_l2


def build_daily_clusters(conn, date: str, sim_threshold: float = 0.86, k: int = 25) -> list[dict]:
    """Group user prompts for a given date into clusters.

    Args:
        conn: SQLite connection.
        date: YYYY-MM-DD.
        sim_threshold: Minimum cosine similarity to attach to a cluster.
        k: Max neighbors to consider per seed.

    Returns:
        List of clusters: {"seed_id": int, "members": [int], "cluster_hint": str}
    """
    # Seeds: all user prompts for that date
    seeds = [
        int(r["id"])
        for r in conn.execute(
            "SELECT id FROM prompt_raw WHERE role='user' AND ts LIKE ? ORDER BY id",
            (f"{date}%",),
        )
    ]
    assigned = set()
    clusters: list[dict] = []
    for sid in seeds:
        if sid in assigned:
            continue
        # Query using the seed's own stored vector by MATCH against itself:
        # fetch vector value by performing a self-match top-K, then compute cosine approx
        # Build a JSON vector by selecting the nearest embedding row (same item_id)
        vrow = conn.execute(
            "SELECT rowid, embedding FROM embeddings WHERE kind='raw' AND item_id=?",
            (sid,),
        ).fetchone()
        if not vrow:
            continue
        emb = vrow["embedding"]
        knn = vec_knn(conn, emb, "raw", k=k)
        members = []
        for item_id, dist in knn:
            cos = cosine_from_l2(dist)
            if cos >= sim_threshold:
                members.append(item_id)
        if not members:
            continue
        # Mark and hint
        assigned.update(members)
        first_text = conn.execute("SELECT text FROM prompt_raw WHERE id=?", (sid,)).fetchone()
        hint = first_text["text"][:80] if first_text else ""  # simple hint
        clusters.append({"seed_id": sid, "members": sorted(set(members)), "cluster_hint": hint})
    return clusters

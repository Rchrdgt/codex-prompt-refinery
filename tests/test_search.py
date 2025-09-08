from pdr.db import connect, create_schema
from pdr.search import hybrid_search


def test_hybrid_search_fts_only():
    """Hybrid search returns FTS results when vector disabled."""
    db = connect(":memory:")
    create_schema(db)
    # Insert raw rows + FTS
    cur = db.execute(
        "INSERT INTO prompt_raw(source_path, role, ts, text, canonical_hash) VALUES (?,?,?,?,?)",
        ("x", "user", "2025-09-07T00:00:00Z", "build a dockerfile for python", "h1"),
    )
    rid = cur.lastrowid
    db.execute(
        "INSERT INTO prompt_raw_fts(rowid, text) VALUES (?,?)",
        (rid, "build a dockerfile for python"),
    )
    cur = db.execute(
        "INSERT INTO prompt_optimized(kind, title, text_md) VALUES (?,?,?)",
        ("atomic", "Dockerfile", "```markdown\nmake a Dockerfile\n```"),
    )
    oid = cur.lastrowid
    db.execute(
        "INSERT INTO prompt_opt_fts(rowid, text_md) VALUES (?,?)", (oid, "make a Dockerfile")
    )
    db.commit()
    res = hybrid_search(db, "dockerfile", topn_fts=10, topk_vec=0)
    assert res["raw"] and res["optimized"]

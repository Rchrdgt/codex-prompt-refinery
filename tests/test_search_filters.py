from pdr.db import connect, create_schema
from pdr.search import hybrid_search


def _seed_raw(db):
    # id1: user, session s1, matches 'hello'
    cur = db.execute(
        "INSERT INTO prompt_raw(source_path, role, ts, text, canonical_hash) VALUES (?,?,?,?,?)",
        ("x", "user", "2025-09-06T00:00:00Z", "hello world", "h1"),
    )
    rid1 = int(cur.lastrowid)
    db.execute("INSERT INTO prompt_raw_fts(rowid, text) VALUES (?,?)", (rid1, "hello world"))

    # id2: assistant, session s2, matches 'hello'
    cur = db.execute(
        (
            "INSERT INTO prompt_raw(source_path, role, ts, text, canonical_hash, session_id) "
            "VALUES (?,?,?,?,?,?)"
        ),
        ("x", "assistant", "2025-09-07T00:00:00Z", "hello assistant", "h2", "s2"),
    )
    rid2 = int(cur.lastrowid)
    db.execute("INSERT INTO prompt_raw_fts(rowid, text) VALUES (?,?)", (rid2, "hello assistant"))

    # id3: system, session s1, non-match
    cur = db.execute(
        (
            "INSERT INTO prompt_raw(source_path, role, ts, text, canonical_hash, session_id) "
            "VALUES (?,?,?,?,?,?)"
        ),
        ("x", "system", "2025-09-05T00:00:00Z", "not a hit", "h3", "s1"),
    )
    rid3 = int(cur.lastrowid)
    db.execute("INSERT INTO prompt_raw_fts(rowid, text) VALUES (?,?)", (rid3, "not a hit"))
    # id4: user; contains keyword 'opt' to exercise union case
    cur = db.execute(
        (
            "INSERT INTO prompt_raw(source_path, role, ts, text, canonical_hash, session_id) "
            "VALUES (?,?,?,?,?,?)"
        ),
        ("x", "user", "2025-09-07T12:00:00Z", "raw mentions opt here", "h4", "s3"),
    )
    rid4 = int(cur.lastrowid)
    db.execute(
        "INSERT INTO prompt_raw_fts(rowid, text) VALUES (?,?)", (rid4, "raw mentions opt here")
    )

    return rid1, rid2, rid3, rid4


def _seed_opt(db):
    # oid1 atomic: matches 'opt'
    cur = db.execute(
        "INSERT INTO prompt_optimized(kind, title, text_md, created_at) VALUES (?,?,?,?)",
        ("atomic", "T1", "opt content", "2025-09-06T00:00:00Z"),
    )
    oid1 = int(cur.lastrowid)
    db.execute("INSERT INTO prompt_opt_fts(rowid, text_md) VALUES (?,?)", (oid1, "opt content"))

    # oid2 workflow: matches 'opt'
    cur = db.execute(
        "INSERT INTO prompt_optimized(kind, title, text_md, created_at) VALUES (?,?,?,?)",
        ("workflow", "T2", "other opt text", "2025-09-07T00:00:00Z"),
    )
    oid2 = int(cur.lastrowid)
    db.execute("INSERT INTO prompt_opt_fts(rowid, text_md) VALUES (?,?)", (oid2, "other opt text"))

    return oid1, oid2


def test_hybrid_search_filters_on_raw_and_optimized():
    """Test hybrid search with filters on raw and optimized prompts."""
    db = connect(":memory:")
    create_schema(db)
    _seed_raw(db)
    _seed_opt(db)
    db.commit()

    filters = {
        "version": 1,
        "where": {
            "ts": {"from": "2025-09-06", "to": "2025-09-07"},
            "roles": ["user"],
            "sessions": [],
            "kind": ["atomic"],
        },
    }
    res = hybrid_search(db, "opt", topn_fts=10, topk_vec=0, filters=filters)
    assert res["optimized"]  # should include atomic only
    for r in res["optimized"]:
        # verify we didn't accidentally include workflow by text
        row = db.execute("SELECT kind FROM prompt_optimized WHERE id=?", (int(r["id"]),)).fetchone()
        assert row and row["kind"] == "atomic"

    # For raw: search 'hello' within ts window and role user
    res2 = hybrid_search(db, "hello", topn_fts=10, topk_vec=0, filters=filters)
    assert res2["raw"]
    for r in res2["raw"]:
        row = db.execute("SELECT role FROM prompt_raw WHERE id=?", (int(r["id"]),)).fetchone()
        assert row and row["role"] == "user"


def test_hybrid_search_no_filters_returns_both():
    """Test hybrid search without filters returns both raw and optimized results."""
    db = connect(":memory:")
    create_schema(db)
    _seed_raw(db)
    _seed_opt(db)
    db.commit()
    res = hybrid_search(db, "opt", topn_fts=10, topk_vec=0)
    # We seeded a raw row that also mentions 'opt' to ensure both non-empty
    assert res["raw"] and res["optimized"]


def test_hybrid_search_vector_path_safe_without_sqlite_vec():
    """Test hybrid search vector path is safe without sqlite-vec."""
    db = connect(":memory:")
    create_schema(db)
    _seed_raw(db)
    # Not seeding optimized here; vector may be unavailable; ensure no exception
    db.commit()
    res = hybrid_search(db, "hello", topn_fts=10, topk_vec=5)
    # Should at least include FTS results
    assert res["raw"]

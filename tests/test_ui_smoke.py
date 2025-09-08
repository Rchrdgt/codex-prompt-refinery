import os
import sys

import pytest
from streamlit.testing.v1 import AppTest

from pdr.db import connect, create_schema


def _seed_minimal(db):
    # Raw row + FTS entry
    cur = db.execute(
        (
            "INSERT INTO prompt_raw(source_path, role, ts, text, canonical_hash, session_id) "
            "VALUES (?,?,?,?,?,?)"
        ),
        ("x", "user", "2025-09-06T00:00:00Z", "smoke raw text", "h1", "s1"),
    )
    rid = int(cur.lastrowid)
    db.execute("INSERT INTO prompt_raw_fts(rowid, text) VALUES (?,?)", (rid, "smoke raw text"))
    # Optimized row + FTS entry
    cur = db.execute(
        "INSERT INTO prompt_optimized(kind, title, text_md, created_at) VALUES (?,?,?,?)",
        ("atomic", "T1", "smoke opt text", "2025-09-06T00:00:00Z"),
    )
    oid = int(cur.lastrowid)
    db.execute("INSERT INTO prompt_opt_fts(rowid, text_md) VALUES (?,?)", (oid, "smoke opt text"))
    db.commit()


@pytest.mark.skipif(AppTest is None, reason="streamlit testing API unavailable")
def test_ui_smoke_renders(tmp_path):
    """Minimal smoke test that the UI script renders without exceptions."""
    db_path = tmp_path / "ui.sqlite"
    os.environ["PDR_DB"] = str(db_path)
    db = connect(str(db_path))
    create_schema(db)
    _seed_minimal(db)

    # Ensure repo root is on sys.path so 'pdr' is importable when AppTest runs
    repo_root = str(tmp_path.cwd() if hasattr(tmp_path, "cwd") else os.getcwd())
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    at = AppTest.from_file("src/pdr/ui.py")
    at.run(timeout=15)
    # AppTest.exception can be an ElementList; treat emptiness as no exception
    exc = getattr(at, "exception", None)
    assert not exc

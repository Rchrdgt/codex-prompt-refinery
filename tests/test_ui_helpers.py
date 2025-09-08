"""Test UI helpers."""

import os

import streamlit as st

from pdr.db import connect, create_schema, view_insert
from pdr.ui import (
    _encode_view_url,
    _get_view_id_from_url,
    _hydrate_filters_from_view,
    _recent_filtered,
)

# Test constants
TEST_VIEW_ID = 123


def _seed(db):
    """Seed test database with sample data."""
    # Raw
    db.execute(
        "INSERT INTO prompt_raw(source_path, role, ts, text, canonical_hash, session_id) "
        "VALUES (?,?,?,?,?,?)",
        ("x", "user", "2025-09-06T00:00:00Z", "A", "h1", "s1"),
    )
    db.execute(
        "INSERT INTO prompt_raw(source_path, role, ts, text, canonical_hash, session_id) "
        "VALUES (?,?,?,?,?,?)",
        ("x", "assistant", "2025-09-07T00:00:00Z", "B", "h2", "s2"),
    )
    # Optimized
    db.execute(
        "INSERT INTO prompt_optimized(kind, title, text_md, created_at) VALUES (?,?,?,?)",
        ("atomic", "T1", "opt1", "2025-09-06T00:00:00Z"),
    )
    db.execute(
        "INSERT INTO prompt_optimized(kind, title, text_md, created_at) VALUES (?,?,?,?)",
        ("workflow", "T2", "opt2", "2025-09-07T00:00:00Z"),
    )
    db.commit()


def test_recent_filtered_respects_facets():
    """Test that recent filtered respects facet filters."""
    db = connect(":memory:")
    create_schema(db)
    _seed(db)
    filters = {
        "version": 1,
        "where": {
            "ts": {"from": "2025-09-06", "to": "2025-09-07"},
            "roles": ["user"],
            "sessions": ["s1"],
            "kind": ["atomic"],
        },
    }
    out = _recent_filtered(db, filters, limit=50)
    assert out["raw"] and out["optimized"]


def test_encode_view_url_env(monkeypatch):
    """Test view URL encoding with environment variables."""
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.com/app")
    url = _encode_view_url(42)
    assert url.startswith("https://example.com/app") and "view=42" in url


def test_hydrate_filters_from_view_sets_session_state():
    """Test hydrating filters from view sets session state."""
    db = connect(":memory:")
    create_schema(db)
    vid = view_insert(db, "V", "both", os.linesep.join(["{", '  "version": 1', "}"]), None)
    # Overwrite with correct JSON to avoid formatting pitfalls in a single write
    db.execute("UPDATE ui_view SET filters_json=? WHERE id=?", ("{}", vid))
    db.commit()
    # Set a known JSON
    db.execute("UPDATE ui_view SET filters_json=? WHERE id=?", ('{"version":1}', vid))
    db.commit()
    # Clear state before hydrating
    st.session_state.clear()
    _hydrate_filters_from_view(db, vid)
    assert st.session_state.get("ui_current_view_id") == vid
    assert st.session_state.get("ui_filters_preload") == {"version": 1}


def test_get_view_id_from_url_roundtrip(monkeypatch):
    """Test roundtrip of getting view ID from URL."""
    # Simulate query params in bare mode via monkeypatch
    monkeypatch.setattr(st, "experimental_get_query_params", lambda: {})
    assert _get_view_id_from_url() is None
    monkeypatch.setattr(st, "experimental_get_query_params", lambda: {"view": [str(TEST_VIEW_ID)]})
    assert _get_view_id_from_url() == TEST_VIEW_ID

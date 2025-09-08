"""SQLite connection, schema, and helpers."""

# ruff: noqa: PLC0415  # allow import-inside-function for optional sqlite-vec

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable, Sequence
from contextlib import suppress


def connect(db_path: str) -> sqlite3.Connection:
    """Create or open a SQLite connection with sane pragmas and load sqlite-vec.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        SQLite connection with pragmas applied and sqlite-vec attempted.
    """
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    _load_sqlite_vec(conn)
    return conn


def _load_sqlite_vec(conn: sqlite3.Connection) -> None:
    """Attempt to load sqlite-vec extension."""
    try:
        import sqlite_vec  # type: ignore  # pylint: disable=import-outside-toplevel

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except (ImportError, sqlite3.OperationalError):
        # Graceful degradation: vector search disabled.
        pass


def create_schema(conn: sqlite3.Connection, embed_dims: int = 1536) -> None:
    """Create day-1 schema if not exists.

    Args:
        conn: SQLite connection.
        embed_dims: Embedding vector dimension.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS prompt_raw (
          id INTEGER PRIMARY KEY,
          source_path TEXT NOT NULL,
          session_id TEXT,
          conversation_id TEXT,
          role TEXT CHECK(role IN ('user','assistant','system')),
          ts TEXT,
          text TEXT NOT NULL,
          canonical_hash TEXT NOT NULL,
          raw_json TEXT
        );

        CREATE TABLE IF NOT EXISTS prompt_optimized (
          id INTEGER PRIMARY KEY,
          kind TEXT CHECK(kind IN ('atomic','workflow')) NOT NULL,
          title TEXT,
          text_md TEXT NOT NULL,
          variables_json TEXT,
          io_contract_json TEXT,
          rationale TEXT,
          created_at TEXT,
          cluster_hint TEXT,
          gpt_meta_json TEXT
        );

        CREATE TABLE IF NOT EXISTS prompt_link (
          optimized_id INTEGER,
          raw_id INTEGER,
          PRIMARY KEY (optimized_id, raw_id)
        );

        -- Saved Views for UI (versioned JSON filter + optional grid state)
        CREATE TABLE IF NOT EXISTS ui_view (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          scope TEXT CHECK(scope IN ('raw','optimized','both')) NOT NULL DEFAULT 'both',
          filters_json TEXT NOT NULL,
          grid_state_json TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT
        );
        """
    )
    # FTS5 (with graceful fallback to regular tables if unavailable)
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS prompt_raw_fts USING fts5(text);")
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS prompt_opt_fts USING fts5(text_md);")
    except sqlite3.OperationalError:
        # FTS5 unavailable; create simple tables to keep API compatible
        conn.execute(
            "CREATE TABLE IF NOT EXISTS prompt_raw_fts(rowid INTEGER PRIMARY KEY, text TEXT);"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS prompt_opt_fts(rowid INTEGER PRIMARY KEY, text_md TEXT);"
        )
    # sqlite-vec vec0 table (rowid used as id)
    with suppress(sqlite3.OperationalError):
        conn.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS embeddings USING vec0(
              embedding float[{embed_dims}],
              kind TEXT,
              item_id INTEGER
            );
            """
        )
    conn.commit()


def view_insert(
    conn: sqlite3.Connection,
    name: str,
    scope: str,
    filters_json: str,
    grid_state_json: str | None = None,
) -> int:
    """Insert a saved view and return its id.

    Args:
        conn: SQLite connection.
        name: View name.
        scope: 'raw' | 'optimized' | 'both'.
        filters_json: Versioned filter JSON string.
        grid_state_json: Optional grid state JSON string.
    """
    cur = conn.execute(
        """
        INSERT INTO ui_view(name, scope, filters_json, grid_state_json)
        VALUES(?,?,?,?)
        """,
        (name, scope, filters_json, grid_state_json),
    )
    conn.commit()
    return int(cur.lastrowid)


def view_get(conn: sqlite3.Connection, view_id: int) -> dict | None:
    """Fetch a saved view by id as a dict (or None)."""
    r = conn.execute(
        (
            "SELECT id, name, scope, filters_json, grid_state_json, created_at, updated_at "
            "FROM ui_view WHERE id=?"
        ),
        (view_id,),
    ).fetchone()
    return dict(r) if r else None


def view_list(conn: sqlite3.Connection) -> list[dict]:
    """Return all views (id, name, scope) ordered by created_at DESC."""
    rows = conn.execute(
        "SELECT id, name, scope, created_at FROM ui_view ORDER BY created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def view_delete(conn: sqlite3.Connection, view_id: int) -> None:
    """Delete a saved view by id."""
    conn.execute("DELETE FROM ui_view WHERE id=?", (view_id,))
    conn.commit()


def fts_insert(conn: sqlite3.Connection, table: str, rowid: int, text: str) -> None:
    """Insert duplicate text into FTS table.

    Args:
        conn: SQLite connection.
        table: Either 'prompt_raw_fts' or 'prompt_opt_fts'.
        rowid: Rowid to mirror (kept in sync by implicit rowid).
        text: Text to index.
    """
    col = "text" if table == "prompt_raw_fts" else "text_md"
    conn.execute(
        f"INSERT INTO {table}(rowid, {col}) VALUES (?,?)",
        (rowid, text),
    )


def vec_insert(conn: sqlite3.Connection, vector_json: str, kind: str, item_id: int) -> int | None:
    """Insert an embedding row into vec0 table.

    Args:
        conn: SQLite connection.
        vector_json: JSON string representation of vector (or serialized blob).
        kind: 'raw' or 'optimized'.
        item_id: Linked item id (prompt_raw.id or prompt_optimized.id).

    Returns:
        Rowid of inserted vector or None if vec0 unavailable.
    """
    try:
        cur = conn.execute(
            "INSERT INTO embeddings(embedding, kind, item_id) VALUES (?, ?, ?)",
            (vector_json, kind, item_id),
        )
        return int(cur.lastrowid)
    except sqlite3.OperationalError:
        return None


def vec_knn(
    conn: sqlite3.Connection, query_vec_json: str, kind: str = "raw", k: int = 20
) -> Sequence[tuple[int, float]]:
    """Run a KNN query against vec0.

    Args:
        conn: SQLite connection.
        query_vec_json: JSON string vector to search.
        kind: Row kind.
        k: Max results.

    Returns:
        Sequence of (item_id, distance).
    """
    try:
        cur = conn.execute(
            """
            SELECT item_id, distance
            FROM embeddings
            WHERE kind=?
              AND embedding MATCH ?
            ORDER BY distance
            LIMIT ?;
            """,
            (kind, query_vec_json, k),
        )
        return [(int(r["item_id"]), float(r["distance"])) for r in cur.fetchall()]
    except sqlite3.OperationalError:
        return []


def bulk_execute(conn: sqlite3.Connection, sql: str, rows: Iterable[tuple]) -> None:
    """Execute executemany with commit.

    Args:
        conn: SQLite connection.
        sql: SQL with placeholders.
        rows: Iterable of tuples.
    """
    conn.executemany(sql, list(rows))
    conn.commit()

"""Typer CLI wiring."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import typer

from .cluster import build_daily_clusters

# from .config import get_settings  # ensure .env is loaded
from .db import connect, create_schema
from .embed import embed_new_user_prompts
from .ingest import ingest_paths
from .synthesize import synthesize_for_clusters

app = typer.Typer(add_completion=False, no_args_is_help=True)

# Default path for ingest command
DEFAULT_INGEST_PATHS = typer.Option(
    ["~/.codex/**"], "--path", help="Glob(s) for JSON/JSONL under ~/.codex"
)


@app.command()
def ingest(
    date: str | None = typer.Option(None, "--date", help="YYYY-MM-DD"),
    since: int | None = typer.Option(None, "--since", min=0, help="Days back by file mtime"),
    path: list[str] = DEFAULT_INGEST_PATHS,
    db: str = typer.Option(os.path.expanduser("~/.pdr.sqlite"), "--db", help="SQLite DB path"),
) -> None:
    """Ingest Codex CLI histories into SQLite with FTS."""
    conn = connect(db)
    create_schema(conn)
    count = ingest_paths(conn, path, date=date, since_days=since)
    typer.echo(f"inserted={count}")


@app.command()
def synthesize(
    date: str = typer.Option(..., "--date", help="YYYY-MM-DD"),
    model: str | None = typer.Option(None, "--model", help="LLM model id"),
    dims: int | None = typer.Option(None, "--dims", help="Embedding dims override"),
    db: str = typer.Option(os.path.expanduser("~/.pdr.sqlite"), "--db", help="SQLite DB path"),
) -> None:
    """Embed, cluster, and synthesize prompts for a date."""
    conn = connect(db)
    create_schema(conn)
    # Embed any missing user prompts
    embed_new_user_prompts(conn, dimensions=dims)
    # Clusters
    clusters = build_daily_clusters(conn, date=date)
    # Synthesize
    inserted = synthesize_for_clusters(conn, clusters, model=model)
    typer.echo(f"optimized_inserted={inserted}")


@app.command()
def ui(
    port: int = typer.Option(8501, "--port", help="Streamlit port"),
    db: str = typer.Option(os.path.expanduser("~/.pdr.sqlite"), "--db", help="SQLite DB path"),
) -> None:
    """Launch Streamlit UI."""
    env = os.environ.copy()
    env["PDR_DB"] = db

    # Ensure package imports work when running the script path.
    # Add repo 'src' to PYTHONPATH.
    src_dir = str(Path(__file__).resolve().parents[2])  # .../src
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [env.get("PYTHONPATH", ""), src_dir]))

    app_path = os.path.join(os.path.dirname(__file__), "ui.py")
    subprocess.run(
        ["streamlit", "run", app_path, "--server.port", str(port), "--server.headless", "true"],
        check=True,
        env=env,
    )

"""Typer CLI wiring."""

from __future__ import annotations

import os
import subprocess

import typer

from .cluster import build_daily_clusters
from .db import connect, create_schema
from .embed import embed_new_user_prompts
from .ingest import ingest_paths
from .synthesize import synthesize_for_clusters

app = typer.Typer(add_completion=False, no_args_is_help=True)

# Typer option singletons to avoid B008 lint in defaults
DATE_OPT = typer.Option(None, "--date", help="YYYY-MM-DD")
SINCE_OPT = typer.Option(None, "--since", min=0, help="Days back by file mtime")
PATH_OPT = typer.Option(["~/.codex/**"], "--path", help="Glob(s) for JSON/JSONL under ~/.codex")
DB_OPT = typer.Option(os.path.expanduser("~/.pdr.sqlite"), "--db", help="SQLite DB path")

DATE_REQ_OPT = typer.Option(..., "--date", help="YYYY-MM-DD")
MODEL_OPT = typer.Option("gpt-5-mini", "--model", help="OpenAI model id")
DIMS_OPT = typer.Option(None, "--dims", help="Embedding dims override")
PORT_OPT = typer.Option(8501, "--port", help="Streamlit port")


@app.command()
def ingest(
    date: str | None = DATE_OPT,
    since: int | None = SINCE_OPT,
    path: list[str] = PATH_OPT,
    db: str = DB_OPT,
) -> None:
    """Ingest Codex CLI histories into SQLite with FTS."""
    conn = connect(db)
    create_schema(conn)
    count = ingest_paths(conn, path, date=date, since_days=since)
    typer.echo(f"inserted={count}")


@app.command()
def synthesize(
    date: str = DATE_REQ_OPT,
    model: str = MODEL_OPT,
    dims: int | None = DIMS_OPT,
    db: str = DB_OPT,
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
    port: int = PORT_OPT,
    db: str = DB_OPT,
) -> None:
    """Launch Streamlit UI."""
    env = os.environ.copy()
    env["PDR_DB"] = db
    app_path = os.path.join(os.path.dirname(__file__), "ui.py")
    subprocess.run(
        ["streamlit", "run", app_path, "--server.port", str(port), "--server.headless", "true"],
        check=True,
        env=env,
    )

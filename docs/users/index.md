# User Guide — Codex Prompt Refinery

This tool ingests OpenAI Codex CLI histories, deduplicates and clusters prompts, synthesizes reusable atomic/workflow prompts, and provides hybrid search with a simple UI.

## Requirements

- Python 3.11+ and `uv`
- Optional: `sqlite-vec` for vector KNN (falls back gracefully)
- OpenAI key for embeddings/synthesis: `OPENAI_API_KEY`

## Quick Start

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev,ui]"

# Ingest recent logs (defaults to ~/.codex/**)
pdr ingest --since 1

# Synthesize prompts for today (uses Responses API)
pdr synthesize --date "$(date -I)" --model gpt-5-mini

# Launch UI on http://localhost:8501
pdr ui --port 8501
```

## Configuration

- `OPENAI_API_KEY`: required for embeddings/synthesis and semantic search
- `PDR_DB`: SQLite path (default `~/.pdr.sqlite`)

## Data & Privacy

- Sources: `~/.codex/**` (JSON/JSONL). Redaction removes common secrets (`sk-…`, `AKIA…`), long digit IDs, and truncates stack traces.
- Exact dedupe via canonical text hash; near-dupe gate uses RapidFuzz with conservative thresholds.

## Search & UI

- “Raw” shows user prompt rows; “Optimized” shows synthesized prompts. Copy/download buttons provided.
- Vector search is used when embeddings exist and `sqlite-vec` loads; otherwise keyword (FTS/LIKE) search still works.

## Common Tasks

- Specific date: `pdr ingest --date 2025-09-08 && pdr synthesize --date 2025-09-08`
- Custom input path: `pdr ingest --since 7 --path "~/work/codex-exports/**"`
- Custom DB: `pdr ui --db ~/data/pdr.sqlite`

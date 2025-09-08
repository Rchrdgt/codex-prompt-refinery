# CLI Reference

The CLI uses Typer. Run `pdr --help` or any subcommand with `--help`.

## Commands

### ingest

Ingest JSON/JSONL logs.

```bash
pdr ingest [--since N | --date YYYY-MM-DD] \
  [--path "~/.codex/**" ...] \
  [--db ~/.pdr.sqlite]
```

- `--since N`: include files modified in the last N days.
- `--date`: exact day filter; falls back to file mtime if record timestamp missing.
- `--path`: one or more globs; defaults to `~/.codex/**`.
- `--db`: SQLite path.

### synthesize

Embed missing rows, cluster by day, and synthesize prompts via Responses API.

```bash
pdr synthesize --date YYYY-MM-DD \
  [--model gpt-5-mini] \
  [--dims 1536] \
  [--db ~/.pdr.sqlite]
```

- `--model`: OpenAI model id for Responses API.
- `--dims`: optional embedding dimensions for `text-embedding-3-small`.

### ui

Run Streamlit UI.

```bash
pdr ui [--port 8501] [--db ~/.pdr.sqlite]
```

## Environment Variables

- `OPENAI_API_KEY`: required for embeddings/synthesis.
- `PDR_DB`: default DB path override for the UI.

## Examples

- Seven-day window: `pdr ingest --since 7`
- Different source tree: `pdr ingest --since 1 --path "~/exports/**" --path "~/tmp/*.jsonl"`
- Synthesize yesterday: `pdr synthesize --date "$(date -I -d 'yesterday')"`

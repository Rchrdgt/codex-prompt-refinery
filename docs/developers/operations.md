# Operations & Deployment

## Environment Variables
- `OPENAI_API_KEY`: required for embeddings/synthesis.
- `PDR_DB`: path to SQLite database (default `~/.pdr.sqlite`).

## Running Locally
```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev,ui]"
pdr ingest --since 1
pdr synthesize --date "$(date -I)"
pdr ui --port 8501
```

## Systemd (WSL2 or Linux user services)
```bash
mkdir -p ~/.config/systemd/user
cp contrib/systemd/* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now codex-prompt-refinery.timer
```
The timer runs daily at 03:15, ingesting + synthesizing fresh prompts.

## Backups & Maintenance
- DB is a single SQLite file (`PDR_DB`). Use `sqlite3 .dump` for logical backups.
- Vacuum occasionally: `sqlite3 ~/.pdr.sqlite 'VACUUM;'`.

## Observability
- Streamlit logs to stdout; redirect or use `systemd --user` journal.
- Store `raw_json` for provenance and recovery.


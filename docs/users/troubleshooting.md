# Troubleshooting

Author: Bjorn Melin

## Missing FTS5

- Symptom: `sqlite3.OperationalError: no such module: fts5`
- Behavior: app falls back to `LIKE` search; functionality remains with reduced ranking quality.
- Fix (optional): install SQLite with FTS5 or use system Python that ships with it.

## sqlite-vec Not Installed

- Symptom: vector KNN queries return empty.
- Behavior: app skips vec queries; keyword search still works.
- Fix: install `sqlite-vec` Python package and ensure dynamic extension loading is allowed.

## OpenAI API Issues

- Symptom: no vector results or synthesize fails.
- Check: `echo $OPENAI_API_KEY` (Linux/macOS) or `$env:OPENAI_API_KEY` (Windows PowerShell).
- Rate limits: reduce batch sizes or re-run later.

## No Results After Ingest

- Confirm input paths: `pdr ingest --since 1 --path "~/.codex/**"`.
- Check date filter: use ISO date (e.g., `2025-09-08`).
- Verify DB file used by UI matches `--db` used during ingest.

## Corrupt JSON Lines

- Ingestion is tolerant and wraps invalid lines as pseudo-user entries. Inspect source files if excessive.

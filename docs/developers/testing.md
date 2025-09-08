# Testing Guide

This project uses pytest for tests, ruff for formatting/lint, and pylint as an extra gate.

## Commands

- Format + lint (ruff):
  - `ruff format .`
  - `ruff check . --fix`
- Lint gate (pylint):
  - `pylint --fail-under=9.5 src/pdr tests`
- Run tests (with coverage gate):
  - `make dev` (installs dev extras including pytest-cov)
  - `make test` (runs pytest with `--cov` and `--cov-fail-under=80`)

If you prefer to run pytest directly:

- `. .venv/bin/activate && pytest -q --cov=src/pdr --cov-report=term-missing --cov-fail-under=80`

## Tests Overview

- `tests/test_db_views.py` — CRUD for saved UI views (SQLite table `ui_view`).
- `tests/test_search_filters.py` — Filtering in `hybrid_search`: FTS/LIKE with WHERE predicates and vector KNN post‑filter safety.
- `tests/test_search.py` — Basic hybrid search behavior for FTS.
- `tests/test_ui_helpers.py` — Non‑UI helpers used by UI: recent filtering, URL encoding/decoding, hydrate from saved view.
- `tests/test_ui_smoke.py` — Optional Streamlit AppTest smoke run for `src/pdr/ui.py` (skips if API is unavailable).
- `tests/test_ingest.py`, `tests/test_synthesize_schema.py`, `tests/test_util.py` — Existing suite.

## Patterns & Practices

- Deterministic tests: no timing sleeps, no external network or services.
- In‑memory SQLite for DB tests; seed FTS mirrors explicitly.
- Avoid fragile UI assertions; the smoke test only checks for error‑free render.
- Prefer focused unit tests that validate invariants and SQL WHERE behavior.

## Writing New Tests

- Seed data close to tests; commit before executing queries.
- Test both presence and absence of filters; verify relevant WHERE clauses via outcomes (e.g., roles/kind restricted).
- Keep assertions stable and informative; avoid brittle string/HTML matches.

## Troubleshooting

- If `streamlit.testing.v1` is not available, `tests/test_ui_smoke.py` will skip automatically.
- If FTS5 is unavailable, LIKE fallback is exercised automatically by the code; tests still pass.

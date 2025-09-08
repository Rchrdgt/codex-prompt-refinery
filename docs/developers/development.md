# Developer Guide

Author: Bjorn Melin

## Environment

- Python 3.11+, `uv`.
- Create and activate: `uv venv && source .venv/bin/activate`.
- Install dev/UI extras: `uv pip install -e ".[dev,ui]"`.

## Commands

- Lint/format: `ruff format . && ruff check . --fix`
- Lint gate: `pylint --fail-under=9.5 src/pdr tests`
- Tests: `pytest -q`
- Run UI: `pdr ui --port 8501`

## Branching & Commits

- Conventional commits (feat|fix|docs|chore|test|refactor):
  - Example: `feat(search): implement hybrid FTS + vector search`
- Default branch: `main`; feature branches: `feat/*`, `fix/*`.

## Local Data

- Use `:memory:` DB for tests; for manual testing, set `PDR_DB=./dev.sqlite`.
- Ingest sample data from your `~/.codex/**` or a sandbox folder.

## OpenAI Integration

- Set `OPENAI_API_KEY` to test embeddings/synthesis.
- Keep batch sizes reasonable; handle rate limits by re-running steps.

## Code Touchpoints

- Add schema changes in `db.py` and update docs/tests accordingly.
- Keep fallbacks intact (FTS→LIKE, vec optional) to support diverse environments.

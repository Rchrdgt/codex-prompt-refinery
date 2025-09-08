# Coding Style & Standards

## Language & Types
- Python ≥ 3.11, full type hints. Prefer `pathlib.Path`, f-strings, early returns.

## Formatting & Linting
- `ruff` for formatting and lint rules (see `.ruff.toml`). Max line length 100.
- `pylint` score ≥ 9.5 for `src/pdr` and `tests`.
- Run locally before committing:
  ```bash
  ruff format . && ruff check . --fix
  pylint --fail-under=9.5 src/pdr tests
  ```

## Naming
- Files/modules/functions: `snake_case`; classes: `CapWords`.
- Tests: `test_*.py`, functions `test_*`.

## Exceptions
- Catch specific exceptions; avoid bare `except:`.
- External/optional deps (FTS/sqlite-vec/OpenAI): degrade gracefully.

## Commits & PRs
- Conventional commits; small, focused diffs.
- PRs: summary, rationale, screenshots (UI), and steps to validate.


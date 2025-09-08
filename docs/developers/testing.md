# Testing Guidelines

## Framework
- `pytest` for unit tests. Keep deterministic/offline.
- Use in-memory DB: `connect(":memory:")` and seed rows with SQL.

## Conventions
- Name files `tests/test_*.py`; test functions `test_*`.
- Each test should assert behavior, not implementation details.
- Mock boundaries only (e.g., OpenAI API, filesystem) as needed.

## Running
```bash
pytest -q
```

## Patterns
- Utility functions: small, pure tests (e.g., canonicalization, hashing, cosine).
- Ingest: write temporary JSONL and assert dedupe/date filters.
- Search: seed FTS tables and assert keyword results; vec queries can be skipped in CI.
- Schemas: validate representative JSON against Pydantic models and JSON Schema keys.

## Quality Gates
- `ruff format . && ruff check . --fix`
- `pylint --fail-under=9.5 src/pdr tests`


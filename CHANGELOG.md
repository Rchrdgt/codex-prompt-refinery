# Changelog

Author: Bjorn Melin

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning.

## [0.1.1] - 2025-09-08

### Added

- Streamlit UI: Raw JSON viewer with an expander per prompt. Pretty tree view when JSON; wrapped text fallback when not JSON.
- Streamlit UI: Optimized tab is now the default and first tab.
- Streamlit UI: Specialize flow for optimized prompts: inline input + Generate button, with specialized output shown only after generation.
- Streamlit UI: Per-card Reset button to clear specialization input/output.
- Streamlit UI: Global model selector (sidebar) with optional custom model id override for specialization.
- Streamlit UI: Inline Copy and Download .md controls to save vertical space on both base and specialized prompts.
- Search: Hybrid FTS + vector search now de-duplicates results by id and keeps the highest score.
- UI Filtering: Server-side filters (date/roles/sessions/kind) applied to both FTS and vector paths.
- Saved Views: Persisted in SQLite (`ui_view`) with shareable URLs (`?view=<id>`); optional `PUBLIC_BASE_URL` for absolute links.
- New Tabs: **Table** (native table by default; optional AgGrid via `ENABLE_AGGRID=1`) and **Charts** (minimal counts).
- Tests: Comprehensive suite for views, filtering, UI helpers, and a Streamlit AppTest smoke.
- Quality: Coverage gating (fail-under 80%) via `make test`; docs updated with testing guide.

### Changed

- Ingestion: When a record lacks a timestamp, store the file mtime (ISO 8601) to enable day-based clustering and synthesis.
- Embedding: Skip empty texts and clamp very long inputs before embedding to reduce provider 4xx errors.
- Defaults: Place the Optimized tab before Raw so it is the active view.
- Makefile: `make test` now runs pytest with coverage and an 80% threshold.

### Fixed

- Config: Avoid passing `base_url=None` to the OpenAI client (which previously produced invalid URLs). Only set `base_url` when non-empty.
- Search UI: FTS fallback to LIKE when FTS5 virtual tables are not available (`prompt_raw_fts`, `prompt_opt_fts`).
- Synthesis: Address provider/model mismatches with a Cerebras fallback (`qwen-3-coder-480b`) when appropriate.

### Notes

- Database schema is created automatically on first run; no manual init required.
- By default, the app uses `~/.pdr.sqlite`. You can override to `./data/pdr.sqlite` (recommended for project-local workflows).

## [0.1.0] - 2025-09-01

Initial public release.

[0.1.1]: https://github.com/BjornMelin/codex-prompt-refinery/releases/tag/v0.1.1
[0.1.0]: https://github.com/BjornMelin/codex-prompt-refinery/releases/tag/v0.1.0

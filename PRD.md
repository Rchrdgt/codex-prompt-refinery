# Product Requirements Document — `codex-prompt-refinery`

Author: Bjorn Melin

## 1) Summary

Local tool that ingests **OpenAI Codex CLI** history under `~/.codex/**`, extracts prompts and nearby assistant replies, deduplicates and groups related prompts, and auto-synthesizes **atomic** and **workflow** prompts via the **OpenAI Responses API** using **Structured Outputs**. Single **SQLite** database with **FTS5** keyword search and **sqlite-vec** semantic search. Minimal **Streamlit** UI to search, view, specialize, and copy prompts. Optional daily automation via **systemd** on WSL2.

* Codex CLI: [https://github.com/openai/codex](https://github.com/openai/codex) · Docs: [https://developers.openai.com/codex/cli/](https://developers.openai.com/codex/cli/)
* Responses API: [https://platform.openai.com/docs/api-reference/responses](https://platform.openai.com/docs/api-reference/responses)
* Structured Outputs: [https://platform.openai.com/docs/guides/structured-outputs](https://platform.openai.com/docs/guides/structured-outputs)
* Embeddings guide: [https://platform.openai.com/docs/guides/embeddings](https://platform.openai.com/docs/guides/embeddings)
* `text-embedding-3-small` announcement: [https://openai.com/index/new-embedding-models-and-api-updates/](https://openai.com/index/new-embedding-models-and-api-updates/)
* SQLite FTS5: [https://www.sqlite.org/fts5.html](https://www.sqlite.org/fts5.html)
* sqlite-vec (Python): [https://alexgarcia.xyz/sqlite-vec/python.html](https://alexgarcia.xyz/sqlite-vec/python.html) · Repo: [https://github.com/asg017/sqlite-vec](https://github.com/asg017/sqlite-vec)
* Streamlit API: [https://docs.streamlit.io/develop/api-reference](https://docs.streamlit.io/develop/api-reference)
* Typer: [https://typer.tiangolo.com/](https://typer.tiangolo.com/)
* RapidFuzz: [https://rapidfuzz.github.io/RapidFuzz/](https://rapidfuzz.github.io/RapidFuzz/)
* WSL2 systemd: [https://learn.microsoft.com/windows/wsl/systemd](https://learn.microsoft.com/windows/wsl/systemd)
* systemd timers: [https://www.freedesktop.org/software/systemd/man/systemd.timer.html](https://www.freedesktop.org/software/systemd/man/systemd.timer.html)

## 2) Objectives

* Distill reusable, one-shot prompts to cut repeated follow-ups.
* Local-only. One developer. One-day build.
* Hybrid search: exact (FTS5) + semantic (sqlite-vec).
* Clean UI to browse, edit lightly, copy or download.

## 3) Out of scope

Multi-user, auth/RBAC, cloud deploy, agent frameworks, external vector DBs, permanent daemons.

## 4) Operating assumptions

* Codex CLI config at `~/.codex/config.toml`; histories live under `~/.codex/**` as JSON/JSONL. Upstream notes config here: [README Configuration](https://github.com/openai/codex#readme) and mentions `~/.codex/config.toml`.
* WSL2 Ubuntu with zsh; optional systemd user services: [WSL systemd](https://learn.microsoft.com/windows/wsl/systemd).
* OpenAI API key via env for embeddings and synthesis.

## 5) Functional requirements

### F1. Ingest

* Inputs: default glob `~/.codex/**` for `*.json` and `*.jsonl`.
* Tolerant JSON/JSONL parsing; extract `ts` (ISO8601 or epoch), `role` (`user|assistant|system`), `text`, `session_id`/`conversation_id` when present, and raw line.
* Pair `user` with next `assistant` in same session (forward scan).
* Store raw JSON for provenance.

### F2. Canonicalize & dedupe

* Canonical text: lowercase, collapse whitespace, strip timestamps/UUIDs, truncate stack traces to N lines.
* Exact dedupe: `sha256(canonical_text)`.
* Near-dup gate: RapidFuzz `partial_ratio >= 90`; suppress unless length delta > 15%.

### F3. Embeddings

* Embed `user` prompts and optimized prompts with `text-embedding-3-small` (default 1536-D; allow `dimensions` override).
  Guides: [Embeddings](https://platform.openai.com/docs/guides/embeddings), update post: [New models](https://openai.com/index/new-embedding-models-and-api-updates/).

### F4. Grouping (KISS)

* Per day greedy clustering by cosine ≥ 0.86 using sqlite-vec KNN. Seed by time; attach neighbors above threshold. Save `cluster_hint` from first prompt’s keywords.

### F5. Synthesis (LLM)

* For each cluster, send 3–10 related `user` prompts plus selected `assistant` snippets to **Responses API** using **Structured Outputs** JSON Schema (see §12).
* Return:

  * `optimized_atomic_prompts[]`
  * `optimized_workflow_prompt`
  * `rationale`
* Each prompt includes: `title`, `prompt_markdown` (fenced, copy-ready), `variables[] {name,type,example,description}`, `io_contract {inputs,outputs}`, and `citations[]` of source raw IDs.
* Default model: `gpt-5-mini`. Allow `--model gpt-5`.

### F6. Storage & search

Schema (day-1):

```sql
CREATE TABLE prompt_raw (
  id INTEGER PRIMARY KEY,
  source_path TEXT NOT NULL,
  session_id TEXT,
  conversation_id TEXT,
  role TEXT CHECK(role IN ('user','assistant','system')),
  ts TEXT,
  text TEXT NOT NULL,
  canonical_hash TEXT NOT NULL,
  raw_json TEXT
);

CREATE TABLE prompt_optimized (
  id INTEGER PRIMARY KEY,
  kind TEXT CHECK(kind IN ('atomic','workflow')) NOT NULL,
  title TEXT,
  text_md TEXT NOT NULL,
  variables_json TEXT,
  io_contract_json TEXT,
  rationale TEXT,
  created_at TEXT,
  cluster_hint TEXT,
  gpt_meta_json TEXT
);

CREATE TABLE prompt_link (
  optimized_id INTEGER,
  raw_id INTEGER,
  PRIMARY KEY (optimized_id, raw_id)
);

CREATE VIRTUAL TABLE prompt_raw_fts USING fts5(text);
CREATE VIRTUAL TABLE prompt_opt_fts USING fts5(text_md);

CREATE VIRTUAL TABLE embeddings USING vec0(
  embedding FLOAT[1536],
  kind TEXT CHECK(kind IN ('raw','optimized')),
  item_id INTEGER
);
```

* FTS5: [https://www.sqlite.org/fts5.html](https://www.sqlite.org/fts5.html)
* sqlite-vec usage: declare `vec0`, insert serialized vectors, query with `MATCH` and `ORDER BY distance`:
  [https://alexgarcia.xyz/sqlite-vec/python.html](https://alexgarcia.xyz/sqlite-vec/python.html)

Vector query example:

```sql
SELECT item_id, distance
FROM embeddings
WHERE kind='raw' AND embedding MATCH ?
ORDER BY distance
LIMIT 20;
```

### F7. UI (Streamlit)

* Single page. Search box runs hybrid search (union of FTS top-N and vector top-K) with simple scoring.
* Tabs: **Raw**, **Optimized**. Cards show title/date and actions: **Copy**, **Edit**, **Download**.
* Detail pane shows fenced markdown in `st.code`, a “Specialize” text area, live preview, and Copy/Download.
  Streamlit API: [https://docs.streamlit.io/develop/api-reference](https://docs.streamlit.io/develop/api-reference)
  Optional components:

  * Copy button: `st-copy-to-clipboard` [https://github.com/mmz-001/st-copy-to-clipboard](https://github.com/mmz-001/st-copy-to-clipboard)
  * Editors: `streamlit-ace` [https://github.com/okld/streamlit-ace](https://github.com/okld/streamlit-ace) or `streamlit-code-editor` [https://github.com/bouzidanas/streamlit-code-editor](https://github.com/bouzidanas/streamlit-code-editor)

### F8. CLI (Typer)

```bash
pdr ingest [--date YYYY-MM-DD | --since N] [--path GLOB...]
pdr synthesize [--date YYYY-MM-DD] [--model gpt-5|gpt-5-mini]
pdr ui [--port 8501]
```

Typer docs: [https://typer.tiangolo.com/](https://typer.tiangolo.com/)

### F9. Optional scheduling (WSL2)

* Provide a systemd user service and timer to run `ingest` then `synthesize` daily.
  Enable systemd in WSL2: [https://learn.microsoft.com/windows/wsl/systemd](https://learn.microsoft.com/windows/wsl/systemd)
  Timers manual: [https://www.freedesktop.org/software/systemd/man/systemd.timer.html](https://www.freedesktop.org/software/systemd/man/systemd.timer.html)

## 6) Non-functional

* Local-first. DB < 1 GB for initial days.
* ≤ 5 minutes for \~100 prompts/day.
* Secret redaction via regex before storage and LLM calls.
* Structured logs to stdout; optional rotating file handler.

## 7) Quality gates

* `ruff` and `pylint` clean.
* `pytest` minimal suite passes.
* UI query latency < 150 ms on 10k-row DB.
* CLI idempotent.
* Synthesis JSON validates against the schema in §12.

## 8) Risks & mitigations

* **Log format drift** → tolerant parsing; keep `raw_json`.
* **False merges** → conservative threshold; UI shows cluster sources.
* **Rate limits** → batch embeddings; retry/backoff; small clusters; default to mini model.

## 9) Decision log (KISS/DRY/YAGNI)

* **SQLite + FTS5 + sqlite-vec** over external vector DBs. One file, no servers.
  FTS5: [https://www.sqlite.org/fts5.html](https://www.sqlite.org/fts5.html) · sqlite-vec: [https://github.com/asg017/sqlite-vec](https://github.com/asg017/sqlite-vec)
* **Greedy clustering** over sklearn. Fewer deps; good enough at this scale.
* **Streamlit** over custom web stack. Faster single-day delivery: [https://docs.streamlit.io/](https://docs.streamlit.io/)
* **Typer** over argparse. Better DX: [https://typer.tiangolo.com/](https://typer.tiangolo.com/)
* **RapidFuzz** for near-dupe: [https://rapidfuzz.github.io/RapidFuzz/](https://rapidfuzz.github.io/RapidFuzz/)

## 10) Decision framework (weighted)

| Decision                                                                           | Option     | Leverage 35% | Value 30% | Load 25% | Adapt 10% |   Total |
| ---------------------------------------------------------------------------------- | ---------- | -----------: | --------: | -------: | --------: | ------: |
| Vector store                                                                       | sqlite-vec |            9 |         8 |        8 |         8 | **8.5** |
|                                                                                    | FAISS      |            7 |         7 |        5 |         7 |     6.6 |
| UI                                                                                 | Streamlit  |            8 |         8 |        8 |         7 | **7.9** |
|                                                                                    | Flask+JS   |            6 |         7 |        4 |         8 |     6.1 |
| CLI                                                                                | Typer      |            8 |         8 |        8 |         7 | **7.9** |
|                                                                                    | argparse   |            6 |         7 |        7 |         7 |     6.7 |
| **Rationale:** Highest leverage with lowest maintenance. Library-first. No server. |            |              |           |          |           |         |

## 11) Data model

* `prompt_raw`: one row per ingested message with provenance and canonical hash.
* `prompt_optimized`: synthesized atomic/workflow prompts and metadata.
* `prompt_link`: many-to-many mapping from optimized prompts to source raw rows.
* `prompt_raw_fts`, `prompt_opt_fts`: duplicated text for FTS.
* `embeddings`: `vec0` table with vectors for `raw` and `optimized`.

## 12) Structured Outputs JSON Schema

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["optimized_atomic_prompts","optimized_workflow_prompt","rationale"],
  "properties": {
    "optimized_atomic_prompts": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["title","prompt_markdown","variables","io_contract","citations"],
        "properties": {
          "title": {"type":"string"},
          "prompt_markdown": {"type":"string"},
          "variables": {"type":"array","items":{"type":"object","required":["name"],"properties":{
            "name":{"type":"string"},
            "type":{"type":"string"},
            "example":{"type":"string"},
            "description":{"type":"string"}
          }}}},
          "io_contract": {"type":"object","required":["inputs","outputs"],"properties":{
            "inputs":{"type":"string"},
            "outputs":{"type":"string"}
          }},
          "citations":{"type":"array","items":{"type":"integer"}}
        }
      }
    },
    "optimized_workflow_prompt": {
      "type":"object",
      "required":["title","prompt_markdown","variables","io_contract","citations"],
      "properties":{
        "title":{"type":"string"},
        "prompt_markdown":{"type":"string"},
        "variables":{"type":"array","items":{"type":"object","required":["name"],"properties":{
          "name":{"type":"string"},
          "type":{"type":"string"},
          "example":{"type":"string"},
          "description":{"type":"string"}
        }}}},
        "io_contract":{"type":"object","required":["inputs","outputs"],"properties":{
          "inputs":{"type":"string"},
          "outputs":{"type":"string"}
        }},
        "citations":{"type":"array","items":{"type":"integer"}}
      }
    },
    "rationale":{"type":"string"}
  }
}
```

* Responses API: [https://platform.openai.com/docs/api-reference/responses](https://platform.openai.com/docs/api-reference/responses)
* Structured Outputs guide: [https://platform.openai.com/docs/guides/structured-outputs](https://platform.openai.com/docs/guides/structured-outputs)

## 13) Algorithms

* **Canonicalize(text):** lowercase → strip ISO timestamps/UUIDs → trim stack trace to N lines → collapse whitespace.
* **Near-dup:** `RapidFuzz.partial_ratio(a,b) >= 90` and `abs(|a|-|b|)/|b| ≤ 0.15` → suppress.
* **Clustering:** for each seed id, KNN via sqlite-vec; approximate cosine from L2 for unit-normalized vectors; attach neighbors ≥ 0.86.

## 14) Security and privacy

* Redact secrets (`sk-…`, AWS AKIA keys, long numeric tokens) before storage or LLM calls.
* Store raw JSON for provenance; mark source path and session ids.
* Optional “ZDR” upstream reference for Codex usage: [https://github.com/openai/codex#readme](https://github.com/openai/codex#readme)

## 15) Telemetry and logging

* Structured logs to stdout. Optional rotating file handler.
* Record ingestion counts, embeddings batches, synthesis success/failure, UI search timings.

## 16) CLI UX

* `pdr ingest --date YYYY-MM-DD` or `--since N` and `--path` globs.
* `pdr synthesize --date YYYY-MM-DD --model gpt-5-mini|gpt-5`.
* `pdr ui --port 8501`.

## 17) UI UX

* Search box. Tabs **Raw**/**Optimized**.
* Card → details pane with fenced markdown, “Specialize” text area, live preview, Copy button, and `.md` download.

## 18) Acceptance criteria (Gherkin)

**Feature: Ingest Codex logs**
Scenario: Parse a day’s logs
Given Codex JSON/JSONL files under `~/.codex/` for a specific date
When I run `pdr ingest --date YYYY-MM-DD`
Then rows are inserted into `prompt_raw` and `prompt_raw_fts` without duplicates
And each row stores `source_path`, `role`, `ts`, `text`, `canonical_hash`, and `raw_json`
And the command exits with code 0.

**Feature: Dedupe and near-dup gate**
Scenario: Re-ingest the same files
Given the DB already contains prompts from the files
When I re-run `pdr ingest` on the same paths
Then duplicate canonical hashes are skipped
And near-duplicates with `partial_ratio ≥ 90` are suppressed unless length delta > 15%.

**Feature: Embeddings**
Scenario: Embed new raw prompts
Given new `user` prompts exist without vectors
When I run `pdr synthesize --date YYYY-MM-DD`
Then `embeddings` rows are created with kind=`raw` and 1536-D vectors
And API errors are handled with retry/backoff.

**Feature: Grouping**
Scenario: Greedy clustering
Given embedded prompts for the day
When grouping runs with threshold 0.86
Then clusters contain semantically related prompts
And each cluster stores a `cluster_hint`.

**Feature: Synthesis**
Scenario: Generate optimized prompts
Given grouped clusters with ≥3 related prompts
When synthesis runs via Responses API with Structured Outputs
Then JSON conforms to the schema in §12
And `prompt_optimized` rows are inserted for atomic and workflow prompts
And back-links are written to `prompt_link`.

**Feature: Search**
Scenario: Hybrid search returns relevant rows
Given prompts exist with FTS and vectors
When I search with a keyword and natural language
Then results include FTS matches and cosine-nearest items
And results are ranked by a simple weighted score.

**Feature: UI**
Scenario: Browse, edit, copy
Given the Streamlit app is running
When I search, open a prompt, and type a specialization
Then a live preview updates
And I can copy to clipboard and download a `.md` snippet.

**Feature: CLI and runbook**
Scenario: Commands work end-to-end
Given Python 3.11+
When I run the runbook commands
Then the DB is created, ingest and synthesize complete, and the UI is reachable on the given port.

**Feature: Tooling**
Scenario: Lint and tests
Given the repo root
When I run `ruff` and `pytest`
Then both succeed.

## 19) Runbook (WSL2, zsh)

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pdr ingest --since 1
pdr synthesize --date "$(date -I)" --model gpt-5-mini
pdr ui --port 8501
```

Enable systemd for daily automation: [WSL systemd](https://learn.microsoft.com/windows/wsl/systemd)
Create user units under `~/.config/systemd/user/`; timers ref: [systemd.timer](https://www.freedesktop.org/software/systemd/man/systemd.timer.html)

## 20) References

* Codex CLI repo: [https://github.com/openai/codex](https://github.com/openai/codex) · Product page: [https://developers.openai.com/codex/cli/](https://developers.openai.com/codex/cli/)
* Responses API: [https://platform.openai.com/docs/api-reference/responses](https://platform.openai.com/docs/api-reference/responses) · Migration guide: [https://platform.openai.com/docs/guides/migrate-to-responses](https://platform.openai.com/docs/guides/migrate-to-responses)
* Structured Outputs: [https://platform.openai.com/docs/guides/structured-outputs](https://platform.openai.com/docs/guides/structured-outputs)
* Embeddings: [https://platform.openai.com/docs/guides/embeddings](https://platform.openai.com/docs/guides/embeddings) · New model post: [https://openai.com/index/new-embedding-models-and-api-updates/](https://openai.com/index/new-embedding-models-and-api-updates/)
* SQLite FTS5: [https://www.sqlite.org/fts5.html](https://www.sqlite.org/fts5.html)
* sqlite-vec Python usage: [https://alexgarcia.xyz/sqlite-vec/python.html](https://alexgarcia.xyz/sqlite-vec/python.html) · Repo: [https://github.com/asg017/sqlite-vec](https://github.com/asg017/sqlite-vec)
* Streamlit: [https://docs.streamlit.io/develop/api-reference](https://docs.streamlit.io/develop/api-reference)
* Typer: [https://typer.tiangolo.com/](https://typer.tiangolo.com/)
* RapidFuzz: [https://rapidfuzz.github.io/RapidFuzz/](https://rapidfuzz.github.io/RapidFuzz/)
* WSL systemd: [https://learn.microsoft.com/windows/wsl/systemd](https://learn.microsoft.com/windows/wsl/systemd)
* systemd timers: [https://www.freedesktop.org/software/systemd/man/systemd.timer.html](https://www.freedesktop.org/software/systemd/man/systemd.timer.html)
* Optional Streamlit components:

  * Copy: [https://github.com/mmz-001/st-copy-to-clipboard](https://github.com/mmz-001/st-copy-to-clipboard)
  * Editor (Ace): [https://github.com/okld/streamlit-ace](https://github.com/okld/streamlit-ace)
  * Editor (react-ace): [https://github.com/bouzidanas/streamlit-code-editor](https://github.com/bouzidanas/streamlit-code-editor)

**K/D/Y:**

* KISS: single SQLite file; no servers.
* DRY: shared ingest/canonicalize utils; duplicated text into FTS by design for day-1.
* YAGNI: no background daemon; greedy clustering instead of sklearn.

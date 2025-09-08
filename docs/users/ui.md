# UI Guide

Launch with:

```bash
pdr ui --port 8501
```

Open <http://localhost:8501>.

## Layout

- Tabs: "Raw" (ingested prompts) and "Optimized" (synthesized prompts).
- Search box: accepts keywords or natural language. When embeddings are available, semantic ranking augments keyword matches.

## Actions

- Copy: copies current text (if optional dependency is installed).
- Download: saves fenced markdown to a `.md` file.
- Specialize (Optimized tab): add context/variables; a live preview shows the combined markdown.

## Tips

- If no vector results appear, ensure you’ve run `pdr synthesize` and set `OPENAI_API_KEY`. The app falls back to keyword search automatically.
- To use a different DB file: `PDR_DB=/path/to/pdr.sqlite pdr ui`.

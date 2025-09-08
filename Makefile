.PHONY: install dev lint test ui run ingest synth docs

install:
	uv venv || python -m venv .venv
	. .venv/bin/activate && uv pip install -e .

dev:
	uv venv || python -m venv .venv
	. .venv/bin/activate && uv pip install -e ".[dev,ui]"

lint:
	. .venv/bin/activate && ruff check .
	. .venv/bin/activate && pylint src/pdr || true

test:
	. .venv/bin/activate && pytest -q --cov=src/pdr --cov-report=term-missing --cov-fail-under=80

ui:
	. .venv/bin/activate && pdr ui --port 8501

ingest:
	. .venv/bin/activate && pdr ingest --since 1

synth:
	. .venv/bin/activate && pdr synthesize --date "$$(date -I)" --model gpt-5-mini

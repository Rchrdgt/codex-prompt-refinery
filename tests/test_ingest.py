from pdr.db import connect, create_schema
from pdr.ingest import ingest_paths


def _write_jsonl(tmp_path, name, lines):
    p = tmp_path / name
    with open(p, "w", encoding="utf-8") as fh:
        for obj in lines:
            fh.write(f"{obj}\n")
    return str(p)


def test_ingest_dedup(tmp_path):
    """Two canonical-equal lines dedupe to one row for a given date."""
    db = connect(":memory:")
    create_schema(db)
    # Two equal lines in JSONL (stringified)
    f1 = tmp_path / "day.jsonl"
    with open(f1, "w", encoding="utf-8") as fh:
        fh.write('{"role":"user","text":"Hello WORLD","ts":"2025-09-07T10:00:00Z"}\n')
        fh.write('{"role":"user","text":"hello   world ","ts":"2025-09-07T11:00:00Z"}\n')
    count = ingest_paths(db, [str(f1)], date="2025-09-07")
    assert count == 1
    n = db.execute("SELECT COUNT(*) FROM prompt_raw").fetchone()[0]
    assert n == 1

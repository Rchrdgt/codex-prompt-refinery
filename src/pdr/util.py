"""Utilities: canonicalization, hashing, batching, cosine, redaction."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Sequence

_WS = re.compile(r"\s+")
_TS = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?Z?\b", re.I)
_UUID = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b", re.I
)
_SECRET = re.compile(r"(sk-[A-Za-z0-9]{20,})")
_AWS = re.compile(r"AKIA[0-9A-Z]{16}")
_STACK = re.compile(r"(?s)(Traceback \(most recent call last\):.*)")
_DIGITS_ONLY = re.compile(r"\b\d{6,}\b")


def redact(text: str) -> str:
    """Redact common secrets and IDs.

    Args:
        text: Input text.

    Returns:
        Redacted text.
    """
    t = _SECRET.sub("[REDACTED]", text)
    t = _AWS.sub("[REDACTED]", t)
    t = _DIGITS_ONLY.sub("[REDACTED]", t)
    return t


def canonicalize(text: str, max_stack_lines: int = 25) -> str:
    """Canonicalize text for dedupe.

    Steps:
      - Lowercase
      - Collapse whitespace
      - Drop ISO timestamps and UUIDs
      - Truncate stack traces to N lines

    Args:
        text: Input text.
        max_stack_lines: Max lines of stack trace retained.

    Returns:
        Canonicalized text.
    """
    text = text or ""
    low = text.lower()
    low = _TS.sub(" ", low)
    low = _UUID.sub(" ", low)
    # Truncate stack trace
    m = _STACK.search(low)
    if m:
        head = low[: m.start()]
        tail = "\n".join(m.group(0).splitlines()[:max_stack_lines])
        low = head + tail
    low = _WS.sub(" ", low).strip()
    return low


def sha256_text(text: str) -> str:
    """Return SHA-256 hex of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def batched(seq: Sequence, size: int) -> Iterator[Sequence]:
    """Yield fixed-size batches."""
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def cosine_from_l2(l2_distance: float) -> float:
    """Approximate cosine similarity from L2 distance assuming unit vectors.

    Args:
        l2_distance: L2 distance reported by sqlite-vec.

    Returns:
        Approximate cosine similarity in [-1, 1].
    """
    return 1.0 - (l2_distance * l2_distance) / 2.0


def json_dumps(obj: object) -> str:
    """Compact JSON dump."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

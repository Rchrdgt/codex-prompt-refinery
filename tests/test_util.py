from pdr.util import canonicalize, cosine_from_l2, redact, sha256_text

HASH_HEX_LEN = 64


def test_canonicalize_and_hash():
    """Canonicalization drops timestamps; hashing returns expected hex length."""
    text = "Hello  World  2024-01-01T10:10:10Z TRACE\nTraceback (most recent call last):\nline"
    c = canonicalize(text)
    assert "traceback" in c
    assert "2024" not in c
    h = sha256_text(c)
    assert len(h) == HASH_HEX_LEN


def test_cosine_from_l2_monotonic():
    """Cosine approximation decreases as L2 increases."""
    assert cosine_from_l2(0.0) == 1.0
    assert cosine_from_l2(1.0) < 1.0
    assert cosine_from_l2(2.0) < cosine_from_l2(1.0)


def test_redact():
    """Secrets and AWS keys are redacted."""
    s = "my key sk-ABCDEF1234567890ABCDEF and AKIA1234567890ABCD"
    r = redact(s)
    assert "[REDACTED]" in r

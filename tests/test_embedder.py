"""Tests for embedder module."""

from mnemosyne.embedder import Embedder


def test_hash_embedder():
    """Test deterministic hash fallback."""
    e = Embedder()
    # Force hash fallback by using a non-existent model
    e._provider = "hash"
    e.dim = 384

    vec = e._hash_embed("test")
    assert len(vec) == 384
    # Check normalization
    norm = sum(x * x for x in vec) ** 0.5
    assert abs(norm - 1.0) < 0.01


def test_hash_determinism():
    """Same input should produce same output."""
    e = Embedder()
    e._provider = "hash"
    e.dim = 384

    v1 = e._hash_embed("hello world")
    v2 = e._hash_embed("hello world")
    assert v1 == v2

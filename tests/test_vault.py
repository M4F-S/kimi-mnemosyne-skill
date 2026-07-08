"""Tests for vault module."""

import tempfile
from pathlib import Path

from mnemosyne.vault import VaultManager


def test_vault_write_and_read():
    """Test writing and reading a note."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = VaultManager(tmpdir)
        vault.write_note(
            title="Test Note",
            content="Hello world",
            tags=["test"],
            note_type="concept",
            status="active",
            salience=0.8,
            links=["Other Note"],
        )

        result = vault.read_note("Test Note")
        assert result is not None
        assert "Hello world" in result["raw"]
        assert result["frontmatter"]["tags"] == ["test"]


def test_vault_wiki_links():
    """Test wiki link extraction."""
    vault = VaultManager("/tmp")
    links = vault.extract_wiki_links("See [[Note A]] and [[Note B]]")
    assert links == ["Note A", "Note B"]

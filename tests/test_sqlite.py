"""Tests for SQLite store."""

import tempfile
import os

from mnemosyne.stores.sqlite import SQLiteStore


def test_sqlite_store_init():
    """Test SQLite store initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = SQLiteStore(db_path)
        stats = store.get_stats()
        assert stats["notes"] == 0
        assert stats["links"] == 0


def test_sqlite_upsert_and_search():
    """Test note upsert and keyword search."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = SQLiteStore(db_path)

        note_id = store.upsert_note(
            title="Test Note",
            content="This is a test",
            tags=["test"],
            note_type="concept",
            status="active",
            salience=0.5,
            embedding=[0.1] * 384,
            vault_path="/tmp",
        )
        assert note_id is not None

        results = store.search_keyword("test")
        assert len(results) > 0
        assert results[0]["title"] == "Test Note"

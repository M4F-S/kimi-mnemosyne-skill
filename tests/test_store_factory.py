"""Tests for store factory."""

from mnemosyne.stores import create_store
from mnemosyne.stores.sqlite import SQLiteStore


def test_create_store_fallback():
    """Test store creation falls back to SQLite."""
    import os
    os.environ.pop("MEMORY_DB_DSN", None)
    store = create_store()
    assert isinstance(store, SQLiteStore)

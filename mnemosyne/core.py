"""Unified Memory System — main API class."""

import logging
from typing import List, Dict, Optional

from mnemosyne.vault import VaultManager, VAULT_PATH
from mnemosyne.stores import create_store
from mnemosyne.stores.postgres import DB_DSN
from mnemosyne.embedder import Embedder, EMBEDDING_DIM
from mnemosyne.security import AdmissionControl, SalienceEngine
from mnemosyne.prospective import ProspectiveMemory
from mnemosyne.consolidation import ConsolidationEngine

logger = logging.getLogger("unified-memory")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class UnifiedMemorySystem:
    """
    One class to rule them all.

    Usage:
        memory = UnifiedMemorySystem()
        memory.remember(title="...", content="...")
        results = memory.recall("query")
        memory.remind_me(title="...", trigger_at="...")
        memory.consolidate()
    """

    def __init__(self, vault_path: str = VAULT_PATH, dsn: str = DB_DSN, auto_sync: bool = False) -> None:
        self.vault = VaultManager(vault_path)
        self.db = create_store(dsn)
        self.embedder = Embedder()
        self.admission = AdmissionControl(self.db, self.embedder)
        self.salience = SalienceEngine()
        self.prospective = ProspectiveMemory(self.db)
        self.consolidation = ConsolidationEngine(self.db, self.vault, self.embedder)

        if auto_sync:
            try:
                self.sync()
            except Exception as e:
                logging.warning(f"Auto-sync failed: {e}. Call memory.sync() manually.")

    def remember(
        self,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        note_type: str = "concept",
        links: Optional[List[str]] = None,
        salience: Optional[float] = None,
    ) -> Dict:
        """
        Write a memory. Goes through admission control before persisting.
        Returns: {"success": bool, "note_id": str, "reason": str}
        """
        tags = tags or []
        links = links or []
        is_valid, reason = self.admission.validate(title, content, tags)
        if not is_valid:
            logger.warning(f"Admission rejected: {title} — {reason}")
            return {"success": False, "note_id": None, "reason": reason}

        if salience is None:
            salience = self.salience.score(
                {"type": note_type, "tags": tags}, content, self.db.get_stats()
            )

        self.vault.write_note(title, content, tags, note_type, "active", salience, links)
        embedding = self.embedder.embed([content])[0] if content else [0.0] * EMBEDDING_DIM
        note_id = self.db.upsert_note(
            title,
            content,
            tags,
            note_type,
            "active",
            salience,
            embedding,
            str(self.vault.vault_path),
        )
        self.db.update_links(note_id, links)
        logger.info(f"Remembered: {title} (salience={salience:.2f})")
        return {"success": True, "note_id": note_id, "reason": reason}

    def recall(
        self, query: str, mode: str = "hybrid", top_k: int = 10, filters: Optional[Dict] = None
    ) -> List[Dict]:
        """Search memories. mode: hybrid (default), semantic, keyword, graph."""
        if mode == "semantic":
            emb = self.embedder.embed([query])[0]
            return self.db.search_semantic(emb, top_k, filters)
        elif mode == "keyword":
            return self.db.search_keyword(query, top_k)
        elif mode == "graph":
            return self.db.search_graph(query, depth=2, top_k=top_k)
        else:
            emb = self.embedder.embed([query])[0]
            return self.db.hybrid_search(query, emb, top_k)

    def remind_me(
        self, title: str, trigger_at: str, content: str = "", recurring: Optional[str] = None
    ) -> str:
        """Schedule a future reminder."""
        return self.prospective.schedule(title, content, trigger_at, recurring)

    def check_reminders(self) -> List[Dict]:
        """Get due reminders. Call this periodically."""
        return self.prospective.get_due(window_hours=24)

    def consolidate(self) -> Dict:
        """Run sleep-time consolidation."""
        return self.consolidation.run()

    def sync(self) -> Dict:
        """Sync vault files to database."""
        return self.vault.sync_to_db(self.db, self.embedder)

    def stats(self) -> Dict:
        """Get system statistics."""
        return self.db.get_stats()

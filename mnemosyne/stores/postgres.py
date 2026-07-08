"""PostgreSQL + pgvector store."""

import os
import logging
import threading
from typing import List, Dict, Optional

from mnemosyne.stores.base import MemoryStore

logger = logging.getLogger("unified-memory")

DB_DSN = os.environ.get("MEMORY_DB_DSN", "postgresql://localhost:5432/mnemosyne")


class PgVectorStore(MemoryStore):
    """
    PostgreSQL-backed store with pgvector for semantic search,
    tsvector for keyword search, and recursive CTEs for graph traversal.
    """

    def __init__(self, dsn: str = DB_DSN):
        self.dsn = dsn
        self._local = threading.local()
        self._ensure_schema()

    def _conn(self):
        """Get or create a thread-local connection."""
        if not hasattr(self._local, "conn") or self._local.conn.closed:
            import psycopg2

            self._local.conn = psycopg2.connect(self.dsn)
        return self._local.conn

    def _ensure_schema(self):
        """Create tables and indexes if they don't exist."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
                cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS notes (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        title TEXT NOT NULL,
                        content TEXT NOT NULL DEFAULT '',
                        tags TEXT[] DEFAULT '{}',
                        note_type TEXT NOT NULL DEFAULT 'concept',
                        status TEXT NOT NULL DEFAULT 'active',
                        salience FLOAT DEFAULT 0.5,
                        embedding VECTOR(384),
                        tsv TSVECTOR,
                        vault_path TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        CONSTRAINT unique_title_vault UNIQUE (title, vault_path)
                    );
                """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS links (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        source_note_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
                        target_note_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
                        link_type TEXT DEFAULT 'wiki',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        CONSTRAINT no_self_link CHECK (source_note_id != target_note_id),
                        CONSTRAINT unique_link UNIQUE (source_note_id, target_note_id)
                    );
                """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS prospective (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        title TEXT NOT NULL,
                        content TEXT,
                        trigger_at TIMESTAMPTZ NOT NULL,
                        recurring TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """
                )

                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS notes_embedding_idx
                    ON notes USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64);
                """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS notes_tsv_idx ON notes USING gin (tsv);")
                cur.execute("CREATE INDEX IF NOT EXISTS notes_tags_idx ON notes USING gin (tags);")
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS notes_salience_idx ON notes (salience DESC);"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS prospective_trigger_idx "
                    "ON prospective (trigger_at);"
                )

                cur.execute(
                    """
                    CREATE OR REPLACE FUNCTION notes_fts_update() RETURNS trigger AS $$
                    BEGIN
                        NEW.tsv := setweight(
                            to_tsvector('english', coalesce(NEW.title, '')), 'A'
                        ) || setweight(
                            to_tsvector('english', coalesce(NEW.content, '')), 'B'
                        ) || setweight(
                            to_tsvector(
                                'english',
                                coalesce(array_to_string(NEW.tags, ' '), '')
                            ),
                            'C'
                        );
                        RETURN NEW;
                    END
                    $$ LANGUAGE plpgsql;
                """
                )
                cur.execute(
                    """
                    DROP TRIGGER IF EXISTS notes_fts_trigger ON notes;
                    CREATE TRIGGER notes_fts_trigger
                    BEFORE INSERT OR UPDATE ON notes
                    FOR EACH ROW EXECUTE FUNCTION notes_fts_update();
                """
                )

                conn.commit()
                logger.info("Database schema initialized.")

    def upsert_note(
        self,
        title: str,
        content: str,
        tags: List[str],
        note_type: str,
        status: str,
        salience: float,
        embedding: List[float],
        vault_path: str,
    ) -> str:
        """Insert or update a note. Returns note ID."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notes (
                        title, content, tags, note_type,
                        status, salience, embedding, vault_path
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (title, vault_path) DO UPDATE SET
                        content = EXCLUDED.content,
                        tags = EXCLUDED.tags,
                        note_type = EXCLUDED.note_type,
                        status = EXCLUDED.status,
                        salience = EXCLUDED.salience,
                        embedding = EXCLUDED.embedding,
                        updated_at = NOW()
                    RETURNING id;
                """,
                    (title, content, tags, note_type, status, salience, embedding, vault_path),
                )
                note_id = cur.fetchone()[0]
                conn.commit()
                return note_id

    def delete_note(self, title: str, vault_path: str) -> bool:
        """Delete a note by title."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM notes WHERE title = %s AND vault_path = %s RETURNING id;",
                    (title, vault_path),
                )
                deleted = cur.fetchone()
                conn.commit()
                return deleted is not None

    def search_semantic(
        self, query_embedding: List[float], top_k: int = 10, filters: Optional[Dict] = None
    ) -> List[Dict]:
        """Vector similarity search."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                where = "WHERE status = 'active'"
                params = [query_embedding, query_embedding, top_k]

                if filters:
                    if filters.get("tags"):
                        where += " AND tags && %s"
                        params.append(filters["tags"])
                    if filters.get("note_type"):
                        where += " AND note_type = %s"
                        params.append(filters["note_type"])

                cur.execute(
                    f"""
                    SELECT id, title, content, tags, note_type, salience, vault_path,
                           1 - (embedding <=> %s::vector) AS score
                    FROM notes
                    {where}
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s;
                """,
                    params,
                )

                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    def search_keyword(self, query: str, top_k: int = 10) -> List[Dict]:
        """Full-text search using PostgreSQL tsvector."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, title, content, tags, note_type, salience, vault_path,
                           ts_rank_cd(tsv, plainto_tsquery('english', %s), 32) AS score
                    FROM notes
                    WHERE status = 'active'
                      AND tsv @@ plainto_tsquery('english', %s)
                    ORDER BY score DESC
                    LIMIT %s;
                """,
                    (query, query, top_k),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    def search_graph(self, note_title: str, depth: int = 2, top_k: int = 10) -> List[Dict]:
        """Graph traversal: find notes connected via wiki-links within N hops."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH RECURSIVE graph AS (
                        SELECT n.id, n.title, n.content, n.tags, n.salience, n.vault_path,
                               0 AS depth, n.id AS root_id
                        FROM notes n
                        WHERE n.title = %s AND n.status = 'active'

                        UNION ALL

                        SELECT n2.id, n2.title, n2.content, n2.tags, n2.salience, n2.vault_path,
                               g.depth + 1, g.root_id
                        FROM graph g
                        JOIN links l ON l.source_note_id = g.id
                        JOIN notes n2 ON n2.id = l.target_note_id
                        WHERE n2.status = 'active'
                          AND g.depth < %s
                    )
                    SELECT DISTINCT id, title, content, tags, salience, vault_path, depth
                    FROM graph
                    WHERE depth > 0
                    ORDER BY depth, salience DESC
                    LIMIT %s;
                """,
                    (note_title, depth, top_k),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    def hybrid_search(
        self, query: str, query_embedding: List[float], top_k: int = 10
    ) -> List[Dict]:
        """
        Reciprocal Rank Fusion (RRF) of semantic + keyword + salience signals.
        k=60 is the standard RRF constant.
        """
        semantic = self.search_semantic(query_embedding, top_k=top_k * 2)
        keyword = self.search_keyword(query, top_k=top_k * 2)

        scores: Dict[str, Dict] = {}

        def add_results(results, source, weight):
            for rank, r in enumerate(results, 1):
                nid = str(r["id"])
                if nid not in scores:
                    scores[nid] = dict(r)
                    scores[nid]["rrf_score"] = 0.0
                    scores[nid]["sources"] = []
                scores[nid]["rrf_score"] += weight * (1.0 / (60 + rank))
                scores[nid]["sources"].append(source)

        add_results(semantic, "semantic", 1.0)
        add_results(keyword, "keyword", 0.8)

        for nid in scores:
            scores[nid]["rrf_score"] += scores[nid].get("salience", 0.5) * 0.2

        sorted_results = sorted(scores.values(), key=lambda x: x["rrf_score"], reverse=True)
        return sorted_results[:top_k]

    def update_links(self, note_id: str, wiki_links: List[str]):
        """Update graph edges for a note based on its wiki-links."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM links WHERE source_note_id = %s;", (note_id,))
                for target_title in wiki_links:
                    cur.execute(
                        """
                        INSERT INTO links (source_note_id, target_note_id, link_type)
                        SELECT %s, id, 'wiki' FROM notes
                        WHERE title = %s AND status = 'active'
                        ON CONFLICT (source_note_id, target_note_id) DO NOTHING;
                    """,
                        (note_id, target_title.strip()),
                    )
                conn.commit()

    def get_stats(self) -> Dict:
        """Get vault statistics."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM notes WHERE status = 'active';")
                note_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM links;")
                link_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM prospective WHERE status = 'pending';")
                pending = cur.fetchone()[0]
                return {"notes": note_count, "links": link_count, "pending_reminders": pending}

name: kimi-mnemosyne-skill
description: Persistent AI agent memory using Obsidian markdown vaults with semantic search, graph traversal, wiki-links, security gates, and MCP server compatibility. Triggered by remember this, save to memory, recall memory, search memory, remind me, consolidate memory, memory audit, graph memory, semantic search, prospective memory, salience scoring, admission control.

---

# Mnemosyne Skill for Kimi

Production-grade unified memory for AI agents. Remember conversations, search by meaning, schedule future reminders, and protect against poisoned data. All memories are plain `.md` files you can open in Obsidian or any text editor.

## What It Does

| Feature | What It Means |
|---------|-------------|
| **Markdown Vault** | Plain `.md` files with YAML frontmatter. Human-readable, Git-diffable, portable. |
| **Semantic Search** | Ask "what did we discuss about neural networks?" — finds related ideas even with different words. |
| **Graph Memory** | Notes link via `[[wiki-links]]`. Traverse relationships 2 hops deep. |
| **Security Gate** | Injection detection (MINJA/ADAM guard), near-duplicate check, contradiction flagging. |
| **Salience Scoring** | Important memories persist longer. Auto-calculated from emphasis markers + type. |
| **Prospective Memory** | "Remember to check this in 3 days" — and actually do it. |
| **Sleep Consolidation** | Nightly maintenance: archive stale, fix broken links, merge duplicates. |
| **MCP Server** | Claude Code, Cursor, and any MCP client can read/write memory directly. |
| **SQLite + PostgreSQL** | Works out of the box with SQLite; scales to PostgreSQL + pgvector. |

## Quick Start

```python
from mnemosyne import UnifiedMemorySystem

memory = UnifiedMemorySystem()  # Auto-creates DB schema

# Save a memory
memory.remember(
    title="API Rate Limit Decision",
    content="100 req/min with burst to 200. Alert if p95 > 200ms.",
    tags=["api", "decision"],
    salience=0.9
)

# Search by meaning (not just keywords)
results = memory.recall("rate limiting policy", mode="hybrid", top_k=5)

# Schedule a future reminder
memory.remind_me("Review API metrics", "2026-07-07T09:00:00", recurring="weekly")

# Run nightly maintenance
memory.consolidate()
```

## API Reference

| Function | Purpose | Example |
|----------|---------|---------|
| `remember(title, content, tags=[], salience=0.5)` | Save a memory | `memory.remember("Decision", "We chose X", salience=0.8)` |
| `recall(query, mode="hybrid", top_k=10)` | Search memory | `memory.recall("API rate limit")` |
| `remind_me(title, trigger_at, content="", recurring=None)` | Schedule reminder | `memory.remind_me("Check", "2026-07-07T09:00", recurring="weekly")` |
| `check_reminders()` | Get due reminders | `memory.check_reminders()` |
| `consolidate()` | Nightly maintenance | `memory.consolidate()` |
| `sync()` | Re-index vault files | `memory.sync()` |
| `stats()` | System health | `memory.stats()` |

## MCP Tools (for Claude Code / Cursor)

| Tool | Input | Output |
|------|-------|--------|
| `memory_remember` | title, content, tags, salience | {success, note_id, reason} |
| `memory_recall` | query, mode, top_k | ranked results with RRF score |
| `memory_remind_me` | title, trigger_at, content, recurring | {reminder_id} |
| `memory_audit` | (none) | {notes, links, pending, health} |

## Prerequisites

```bash
# SQLite works out of the box — no setup needed
pip install -e ".[dev]"

# For PostgreSQL (optional, scales better):
# docker run -d --name mnemosyne-pg -p 15432:5432 ankane/pgvector:latest
```

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MEMORY_DB_DSN` | (none) | PostgreSQL connection string |
| `MEMORY_SQLITE_PATH` | `~/.mnemosyne/mnemosyne.db` | SQLite database path |
| `MEMORY_VAULT_PATH` | `~/Documents/Kimi/Workspaces/Mnemosyne/vault` | Markdown vault directory |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server for embeddings |

## Installation

```bash
pip install -e ".[dev]"
```

## File Locations

| File | Purpose |
|------|---------|
| `mnemosyne/` | Python package (import this) |
| `~/Mnemosyne/vault/` | Your notes (source of truth) |
| `~/.mnemosyne/mnemosyne.db` | SQLite database (auto-created) |

## Best Practices

1. **Files are the source of truth.** Edit `.md` files in Obsidian/VS Code. Run `memory.sync()` after external edits.
2. **Use salience wisely.** 0.9 for critical decisions, 0.3 for casual notes. Default 0.5.
3. **Link aggressively.** Every note should connect to at least 2 others via `[[wiki-links]]`.
4. **Run consolidation weekly.** Keeps the vault clean and fast.
5. **Back up the vault.** It's just markdown files. `git init` in the vault directory.

## Full Platform

This is the **Kimi skill** — the minimal installable version. For the full platform with:
- FastAPI REST API
- Next.js frontend dashboard
- Neo4j graph backend
- 20+ platform connectors (Gmail, GitHub, Slack, etc.)
- Stripe billing integration
- Docker Compose deployment
- Team RBAC and multi-tenancy

See: **https://github.com/M4F-S/mnemosyne** (platform repo)

## Architecture

```
┌─────────────────────────────────────────────┐
│         Kimi Desktop / Claude Code           │
│              (MCP Client)                    │
└──────────────────┬──────────────────────────┘
                   │ stdio MCP
┌──────────────────▼──────────────────────────┐
│        kimi-mnemosyne-skill                 │
│  ┌─────────────┐  ┌─────────────────────┐  │
│  │  MCP Server │  │  Memory Operations  │  │
│  │  (4 tools)  │  │  (remember/recall)  │  │
│  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌─────────────────────┐  │
│  │   SQLite    │  │   PostgreSQL        │  │
│  │  (fallback) │  │  (pgvector)         │  │
│  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────┘
         │
         ▼ (optional: full platform)
┌─────────────────────────────────────────────┐
│           mnemosyne (platform)              │
│  ┌─────────┐ ┌─────────┐ ┌───────────────┐ │
│  │ FastAPI │ │ Next.js │ │   Neo4j       │ │
│  │  REST   │ │  Dashboard│ │  (graph)     │ │
│  └─────────┘ └─────────┘ └───────────────┘ │
└─────────────────────────────────────────────┘
```

## License

Apache 2.0

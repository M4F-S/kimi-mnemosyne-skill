"""MCP server (JSON-RPC 2.0 over stdio)."""

import sys
import json
import time
import signal
import logging
from typing import Dict, List, Optional

from mnemosyne.core import UnifiedMemorySystem

logger = logging.getLogger("unified-memory")


class MemoryMCPServer:
    """
    MCP server exposing memory operations as tools.
    Compatible with Claude Code, Cursor, and any MCP client.
    """

    def __init__(self, memory: Optional[UnifiedMemorySystem] = None):
        self._memory = memory
        self._running = False
        self._start_time = time.time()
        self._request_count = 0
        self._error_count = 0

    @property
    def memory(self) -> UnifiedMemorySystem:
        if self._memory is None:
            self._memory = UnifiedMemorySystem(auto_sync=False)
        return self._memory

    def _uptime(self) -> float:
        return time.time() - self._start_time

    def run(self):
        """Main loop: read JSON-RPC requests from stdin, write responses to stdout."""
        self._running = True
        self._setup_signal_handlers()
        logger.info("MCP Memory Server starting...")
        for line in sys.stdin:
            if not self._running:
                break
            line = line.strip()
            if not line:
                continue
            req_id = None
            try:
                req = json.loads(line)
                req_id = req.get("id")
                logger.info(
                    f"[{req_id}] Request: {req.get('method')} "
                    f"params={req.get('params', {})}"
                )
                resp = self._handle(req)
                logger.info(
                    f"[{req_id}] Response: "
                    f"success={resp.get('result') is not None}"
                )
            except json.JSONDecodeError as e:
                self._error_count += 1
                logger.error(f"[{req_id}] JSON parse error: {e}")
                resp = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": str(e)},
                    "id": req_id,
                }
            except Exception as e:
                self._error_count += 1
                logger.error(f"[{req_id}] Unexpected error: {e}")
                resp = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32603, "message": str(e)},
                    "id": req_id,
                }
            print(json.dumps(resp), flush=True)
        logger.info("MCP Memory Server shutting down...")

    def _setup_signal_handlers(self):
        """Handle SIGTERM and SIGINT for graceful shutdown."""
        def _handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self._running = False
        signal.signal(signal.SIGTERM, _handler)
        signal.signal(signal.SIGINT, _handler)

    def _handle(self, req: Dict) -> Dict:
        """Handle a single JSON-RPC request with proper error handling."""
        method = req.get("method")
        params = req.get("params", {})
        req_id = req.get("id")
        self._request_count += 1

        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                    },
                    "id": req_id,
                }
            if method == "tools/list":
                return {
                    "jsonrpc": "2.0",
                    "result": {"tools": self._tools()},
                    "id": req_id,
                }
            if method == "tools/call":
                name = params.get("name", "")
                args = params.get("arguments", {})
                result = self._call_tool(name, args)
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "content": [
                            {"type": "text", "text": json.dumps(result)}
                        ]
                    },
                    "id": req_id,
                }
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
                "id": req_id,
            }
        except Exception as e:
            self._error_count += 1
            logger.error(f"[{req_id}] Tool error in {method}: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(e)},
                "id": req_id,
            }

    def _tools(self) -> List[Dict]:
        return [
            {
                "name": "memory_remember",
                "description": "Save a fact, decision, or observation to persistent memory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "salience": {"type": "number"},
                    },
                    "required": ["title", "content"],
                },
            },
            {
                "name": "memory_recall",
                "description": "Search memory by semantic meaning, keywords, or graph relationships",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "mode": {
                            "type": "string",
                            "enum": ["hybrid", "semantic", "keyword", "graph"],
                        },
                        "top_k": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "memory_remind_me",
                "description": "Schedule a future reminder or recurring task",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "trigger_at": {"type": "string"},
                        "recurring": {
                            "type": "string",
                            "enum": ["daily", "weekly", "monthly"],
                        },
                    },
                    "required": ["title", "trigger_at"],
                },
            },
            {
                "name": "memory_audit",
                "description": "Get memory system statistics and health check",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]

    def _call_tool(self, name: str, args: Dict) -> Dict:
        if name == "memory_remember":
            return self.memory.remember(
                title=args.get("title", ""),
                content=args.get("content", ""),
                tags=args.get("tags", []),
                salience=args.get("salience"),
            )
        elif name == "memory_recall":
            return {
                "results": self.memory.recall(
                    query=args.get("query", ""),
                    mode=args.get("mode", "hybrid"),
                    top_k=args.get("top_k", 5),
                )
            }
        elif name == "memory_remind_me":
            return {
                "reminder_id": self.memory.remind_me(
                    title=args.get("title", ""),
                    trigger_at=args.get("trigger_at", ""),
                    content=args.get("content", ""),
                    recurring=args.get("recurring"),
                )
            }
        elif name == "memory_audit":
            stats = self.memory.stats()
            stats["health"] = self._health()
            return stats
        else:
            return {"error": f"Unknown tool: {name}"}

    def _health(self) -> Dict:
        """Return server health information."""
        store_type = type(self.memory.db).__name__
        embedder_provider = self.memory.embedder._provider or "unknown"
        return {
            "server": {
                "status": "healthy",
                "uptime_seconds": round(self._uptime(), 2),
                "requests": self._request_count,
                "errors": self._error_count,
            },
            "store": {
                "type": store_type,
                "vault_path": str(self.memory.vault.vault_path),
            },
            "embedder": {
                "provider": embedder_provider,
                "model": self.memory.embedder.model_name,
                "dimension": self.memory.embedder.dim,
            },
        }

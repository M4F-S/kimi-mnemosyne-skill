"""Tests for MCP server tools."""

import json
from unittest.mock import MagicMock, patch

from mnemosyne.mcp_server import MemoryMCPServer


def test_tools_list():
    """Test tools/list method."""
    server = MemoryMCPServer()
    req = {"jsonrpc": "2.0", "method": "tools/list", "id": 1}
    resp = server._handle(req)
    assert "result" in resp
    assert "tools" in resp["result"]
    assert len(resp["result"]["tools"]) == 4


def test_initialize():
    """Test initialize method."""
    server = MemoryMCPServer()
    req = {"jsonrpc": "2.0", "method": "initialize", "id": 1}
    resp = server._handle(req)
    assert "result" in resp
    assert resp["result"]["protocolVersion"] == "2024-11-05"


def test_unknown_method():
    """Test unknown method handling."""
    server = MemoryMCPServer()
    req = {"jsonrpc": "2.0", "method": "unknown", "id": 1}
    resp = server._handle(req)
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_memory_remember_tool():
    """Test memory_remember tool."""
    mock_memory = MagicMock()
    mock_memory.remember.return_value = {"success": True, "note_id": "123", "reason": "ok"}

    server = MemoryMCPServer(mock_memory)
    req = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "memory_remember",
            "arguments": {"title": "Test", "content": "Hello"},
        },
        "id": 1,
    }
    resp = server._handle(req)
    assert "result" in resp
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["success"] is True


def test_memory_audit_tool():
    """Test memory_audit tool."""
    mock_memory = MagicMock()
    mock_memory.stats.return_value = {"notes": 5, "links": 3}
    mock_memory.vault.vault_path = "/tmp"
    mock_memory.embedder._provider = "hash"
    mock_memory.embedder.model_name = "test"
    mock_memory.embedder.dim = 384

    server = MemoryMCPServer(mock_memory)
    req = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "memory_audit"},
        "id": 1,
    }
    resp = server._handle(req)
    assert "result" in resp
    content = json.loads(resp["result"]["content"][0]["text"])
    assert "notes" in content
    assert "health" in content

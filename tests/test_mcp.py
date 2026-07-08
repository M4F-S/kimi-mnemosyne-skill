"""Tests for MCP server module."""

from mnemosyne.mcp_server import MemoryMCPServer


def test_mcp_server_init():
    """Test MCP server initialization."""
    server = MemoryMCPServer()
    assert server._running is False
    assert server._request_count == 0
    assert server._error_count == 0

"""Mnemosyne - Local-first memory system for AI agents."""

import logging

__version__ = "0.1.0"

from mnemosyne.core import UnifiedMemorySystem
from mnemosyne.mcp_server import MemoryMCPServer

__all__ = ["UnifiedMemorySystem", "MemoryMCPServer", "__version__"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

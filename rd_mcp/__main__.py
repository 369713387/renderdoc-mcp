"""MCP server main entry point.

This module allows the MCP server to be run as:
    python -m rd_mcp.server
"""
import asyncio
import sys

from .server import main


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)

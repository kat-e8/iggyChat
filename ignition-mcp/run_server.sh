#!/bin/bash
# Launches the Ignition MCP server (streamable HTTP transport, http://localhost:8007/mcp).
# For stdio transport (Claude Desktop subprocess mode), see .mcp.json instead.
set -e
cd "$(dirname "$0")"
uv run python mcp_server.py "$@"

# Troubleshooting Guide

This guide helps diagnose and resolve common issues with the Ignition MCP Server.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Installation Issues](#installation-issues)
- [Connection Problems](#connection-problems)
- [Authentication Errors](#authentication-errors)
- [WebDev Tool Errors](#webdev-tool-errors)
- [Tool Execution Failures](#tool-execution-failures)
- [Claude Code / Claude Desktop Integration Issues](#claude-code--claude-desktop-integration-issues)
- [Common Error Messages](#common-error-messages)
- [Debug Logging](#debug-logging)
- [Getting Help](#getting-help)

## Quick Diagnostics

```bash
# Python version (need 3.10+)
python --version

# Package installed?
uv run python -c "import ignition_mcp; print('ok')"

# Configuration loaded correctly?
uv run python -c "
from ignition_mcp.config import settings
print('Gateway URL:', settings.ignition_gateway_url)
print('API Key:', 'SET' if settings.ignition_api_key else 'NOT SET')
print('WebDev tag endpoint:', settings.webdev_tag_endpoint or '(not configured)')
"

# Live gateway connectivity
uv run python -c "
import asyncio
from ignition_mcp.ignition_client import IgnitionClient

async def test():
    async with IgnitionClient() as client:
        print(await client.get_gateway_info())

asyncio.run(test())
"
```

## Installation Issues

### Python Version Incompatibility

```bash
python --version   # should show 3.10+
```

### Package Installation Failures

```bash
# Reinstall cleanly
uv sync --reinstall
# or
pip install -e ".[dev]" --force-reinstall
```

### `ModuleNotFoundError: No module named 'ignition_mcp'`

Dependencies aren't installed, or you're not running through `uv run` / an activated venv.

```bash
uv sync
# or
source .venv/bin/activate && pip install -e .
```

## Connection Problems

### Gateway Unreachable

**Diagnosis**:
```bash
curl http://gateway-host:8088/data/api/v1/gateway-info
ping gateway-host
nslookup gateway-host
```

**Common fixes**:
- Confirm `IGNITION_MCP_IGNITION_GATEWAY_URL` matches how the gateway is actually reachable
  (`http://localhost:8088`, `https://gateway.company.com:8043`, etc.)
- Confirm the Gateway's REST API module is enabled
- Check firewalls between the MCP server host and the gateway

### SSL/TLS Issues

**Error**: `SSL: CERTIFICATE_VERIFY_FAILED`

```bash
# Development only — accept self-signed certs
IGNITION_MCP_SSL_VERIFY=false

# Or use HTTP instead of HTTPS for local testing
IGNITION_MCP_IGNITION_GATEWAY_URL=http://gateway:8088
```

## Authentication Errors

### `HTTPStatusError: 401 Client Error: Unauthorized`

```bash
# Test the API key manually
curl -H "X-Ignition-API-Token: your_key" http://gateway:8088/data/api/v1/gateway-info

# Test basic auth manually
curl -u username:password http://gateway:8088/data/api/v1/gateway-info
```

- API key takes precedence over basic auth whenever `IGNITION_MCP_IGNITION_API_KEY` is
  non-empty — clear it if you intend to use basic auth instead.
- Regenerate the key from Config → Security → Users, Roles → [User] → API Keys and
  confirm the associated user has the roles the tools need.

## WebDev Tool Errors

Tools backed by WebDev (`read_tags`, `write_tag`, tag CRUD, alarms, `get_tag_history`,
`run_gateway_script`) return a **setup-guidance error** — not a stack trace — when their
endpoint isn't configured. That's expected until you:

1. Deploy the corresponding gateway-side script (see [webdev-setup.md](webdev-setup.md))
2. Set the matching `IGNITION_MCP_WEBDEV_*_ENDPOINT` variable in `.env`
3. Restart the MCP server so it picks up the new setting

If the endpoint *is* configured but calls still fail:

```bash
# Confirm the WebDev resource actually responds
curl -H "X-Ignition-API-Token: your_key" \
  http://gateway:8088/system/webdev/Global/GatewayAPI/tags
```

Check the gateway's own logs (`get_gateway_logs` tool, or the Gateway webpage's
Status → Logs) for errors raised inside the WebDev script itself.

## Tool Execution Failures

### Tool Not Found / Wrong Name

Tool names are fixed by the server (see [api-reference.md](api-reference.md) for the
full list of 37) — there's no dynamic discovery step. Double-check spelling against
that reference, e.g. `list_projects` not `get_projects`.

### Invalid Parameters

Check the parameter table for the specific tool in [api-reference.md](api-reference.md).
Common mistakes:
- `browse_tags` expects a `path` like `[default]Folder`, not a bare tag name
- `read_tags` / `get_tag_history` take a list of fully-qualified tag paths, not a single string
- `create_project` / project tools use plain field names (`name`, `title`, `description`) —
  there's no `body_` prefix convention in this server

### Gateway API Errors (HTTP 400/404)

```bash
# Check recent gateway errors
{"tool": "get_gateway_logs", "arguments": {"level": "ERROR", "limit": 20}}
```

Verify the Ignition version actually supports the endpoint being called (native REST API
requires Ignition 8.3+) and that any referenced project/resource/tag path exists.

## Claude Code / Claude Desktop Integration Issues

### Claude Code Not Detecting Tools

1. Confirm `.mcp.json` exists in the project root and is valid JSON
2. Restart Claude Code / reload the project after editing `.mcp.json` or `.env`
3. Test the server starts cleanly outside Claude Code:
   ```bash
   uv run python mcp_server.py --transport stdio
   ```

### Claude Desktop Not Loading the Server

```bash
# Validate JSON syntax
python -m json.tool ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Run the exact command Claude Desktop uses, manually
uv run python mcp_server.py --transport stdio
```

Make sure `cwd` in the config points at the repo root (`mcp_server.py` needs to find
`src/` relative to itself).

## Common Error Messages

### `ConnectionError` / `httpx.ConnectError`

Gateway unreachable at the configured URL — see [Connection Problems](#connection-problems).

### `ValidationError: 1 validation error for Settings`

An environment variable has the wrong type (e.g. a non-integer `IGNITION_MCP_SERVER_PORT`).
Check `.env` against [configuration.md](configuration.md).

### `ValueError: WebDev tag endpoint not configured...`

Expected — see [WebDev Tool Errors](#webdev-tool-errors).

### `HTTPStatusError: 401 Client Error: Unauthorized`

See [Authentication Errors](#authentication-errors).

## Debug Logging

`mcp_server.py` uses the standard `logging` module under the `ignition-mcp` logger name.
To see more detail, set the level before running:

```bash
uv run python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
import mcp_server
mcp_server.main()
"
```

For HTTP-level detail, also enable `httpx`'s logger:

```python
logging.getLogger('httpx').setLevel(logging.DEBUG)
```

## Getting Help

Before asking for help, gather:

- Full error message / traceback
- Sanitized configuration (redact API keys/passwords)
- Ignition Gateway version and edition
- Whether the failing tool is native-REST or WebDev-backed (see [api-reference.md](api-reference.md))

Then check:
1. [Installation Guide](installation.md)
2. [Configuration Guide](configuration.md)
3. [API Reference](api-reference.md)
4. GitHub Issues for this repository

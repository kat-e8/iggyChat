# Configuration Guide

This guide covers all configuration options for the Ignition MCP Server: environment
variables, authentication methods, WebDev endpoints, and advanced settings.

## Configuration Overview

Settings are loaded via `pydantic-settings` (see `src/ignition_mcp/config.py`) with the
following precedence:

1. **Environment variables** (highest priority)
2. **`.env` file** (medium priority)
3. **Default values** (lowest priority)

All environment variables are prefixed with `IGNITION_MCP_`.

## Environment Variables

### Gateway Connection Settings

#### `IGNITION_MCP_IGNITION_GATEWAY_URL`
- **Description**: Base URL for your Ignition Gateway
- **Default**: `http://localhost:8088`
- **Format**: `http://hostname:port` or `https://hostname:port`

```bash
IGNITION_MCP_IGNITION_GATEWAY_URL=http://localhost:8088
IGNITION_MCP_IGNITION_GATEWAY_URL=https://gateway.example.com:8043
```

### Authentication Settings

Choose **one** of the following:

#### Option 1: API Key Authentication (Recommended)

**`IGNITION_MCP_IGNITION_API_KEY`**
- **Default**: `""` (empty)
- Generate from the Gateway: Config → Security → Users, Roles → [User] → API Keys
- Takes precedence over username/password whenever set

```bash
IGNITION_MCP_IGNITION_API_KEY=IGN-API-KEY-1234567890abcdef
```

#### Option 2: Basic Authentication

**`IGNITION_MCP_IGNITION_USERNAME`** (default: `admin`)
**`IGNITION_MCP_IGNITION_PASSWORD`** (default: `password`)

Used only when no API key is set.

```bash
IGNITION_MCP_IGNITION_USERNAME=gateway_admin
IGNITION_MCP_IGNITION_PASSWORD=secure_password_123
```

### MCP Server Settings

These only apply to the `streamable-http` transport; stdio transport ignores them.

#### `IGNITION_MCP_SERVER_HOST`
- **Default**: `127.0.0.1`
- `0.0.0.0` to bind all interfaces, or a specific IP.

#### `IGNITION_MCP_SERVER_PORT`
- **Default**: `8007`

```bash
IGNITION_MCP_SERVER_HOST=0.0.0.0
IGNITION_MCP_SERVER_PORT=9000
```

### SSL Settings

#### `IGNITION_MCP_SSL_VERIFY`
- **Default**: `true`
- Set `false` to accept self-signed certificates (development only).

### WebDev Endpoints

The native REST API (`/data/api/v1/`) only covers gateway configuration — it does not
expose runtime tag reads/writes, alarms, historian, or script execution. Those tools
require a WebDev module script deployed on the gateway; see
[webdev-setup.md](webdev-setup.md) for the deployment scripts. Each variable takes the
WebDev resource path (e.g. `Global/GatewayAPI/tags`), not a full URL. Leave any of them
empty to disable the corresponding tools — they'll return a setup-guidance error instead
of failing silently.

| Variable | Tools it enables |
|----------|-------------------|
| `IGNITION_MCP_WEBDEV_TAG_ENDPOINT` | `read_tags`, `write_tag` |
| `IGNITION_MCP_WEBDEV_TAG_CONFIG_ENDPOINT` | `get_tag_config`, `create_tags`, `edit_tags`, `delete_tags`, `list_udt_types`, `get_udt_definition` |
| `IGNITION_MCP_WEBDEV_ALARM_ENDPOINT` | `get_active_alarms`, `get_alarm_history`, `acknowledge_alarms` |
| `IGNITION_MCP_WEBDEV_TAG_HISTORY_ENDPOINT` | `get_tag_history` |
| `IGNITION_MCP_WEBDEV_SCRIPT_EXEC_ENDPOINT` | `run_gateway_script` |

```bash
IGNITION_MCP_WEBDEV_TAG_ENDPOINT=Global/GatewayAPI/tags
IGNITION_MCP_WEBDEV_TAG_CONFIG_ENDPOINT=Global/GatewayAPI/tagConfig
IGNITION_MCP_WEBDEV_ALARM_ENDPOINT=Global/GatewayAPI/alarms
IGNITION_MCP_WEBDEV_TAG_HISTORY_ENDPOINT=Global/GatewayAPI/tagHistory
IGNITION_MCP_WEBDEV_SCRIPT_EXEC_ENDPOINT=Global/GatewayAPI/scriptExec
```

#### `IGNITION_MCP_ENABLE_SCRIPT_EXECUTION`
- **Default**: `false`
- Must be explicitly set `true` to enable `run_gateway_script`, even if the endpoint
  above is configured. Off by default for safety — it executes arbitrary Python on
  the gateway.

## Configuration Files

### `.env` File

```bash
IGNITION_MCP_IGNITION_GATEWAY_URL=http://localhost:8088
IGNITION_MCP_IGNITION_API_KEY=your_api_key_here

IGNITION_MCP_SERVER_HOST=127.0.0.1
IGNITION_MCP_SERVER_PORT=8007

IGNITION_MCP_WEBDEV_TAG_ENDPOINT=Global/GatewayAPI/tags
```

## Authentication Setup

### Creating an API Key in Ignition

1. Open the Gateway webpage: `http://your-gateway:8088`
2. Config → Security → Users, Roles
3. Select or create a user
4. Under "API Keys", generate a new key and copy it
5. Set `IGNITION_MCP_IGNITION_API_KEY` to the generated key

### Basic Authentication

Prefer a dedicated user with minimal roles over the default `admin` account,
especially in production.

## Advanced Configuration

### Request Timeout

Hardcoded to 30 seconds in `IgnitionClient.__init__` (`src/ignition_mcp/ignition_client.py`).
To change it, edit the `httpx.AsyncClient(... timeout=30.0 ...)` call directly.

### Proxy Configuration

`httpx` respects standard proxy environment variables:

```bash
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080
export NO_PROXY=localhost,127.0.0.1
```

## Configuration Validation

```bash
# Print resolved settings
uv run python -c "from ignition_mcp.config import settings; print(settings.model_dump())"

# Test the gateway connection
uv run python -c "
import asyncio
from ignition_mcp.ignition_client import IgnitionClient

async def test():
    async with IgnitionClient() as client:
        print(await client.get_gateway_info())

asyncio.run(test())
"
```

## Configuration Examples

### Docker

```yaml
# docker-compose.yml
services:
  ignition-mcp:
    build: .
    environment:
      - IGNITION_MCP_IGNITION_GATEWAY_URL=http://gateway:8088
      - IGNITION_MCP_IGNITION_API_KEY=${IGNITION_API_KEY}
      - IGNITION_MCP_SERVER_HOST=0.0.0.0
      - IGNITION_MCP_SERVER_PORT=8007
    ports:
      - "8007:8007"
```

### Kubernetes ConfigMap / Secret

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ignition-mcp-config
data:
  IGNITION_MCP_IGNITION_GATEWAY_URL: "http://ignition-gateway:8088"
  IGNITION_MCP_SERVER_HOST: "0.0.0.0"
  IGNITION_MCP_SERVER_PORT: "8007"
---
apiVersion: v1
kind: Secret
metadata:
  name: ignition-mcp-secret
type: Opaque
stringData:
  IGNITION_MCP_IGNITION_API_KEY: "your_secret_api_key"
```

## Security Best Practices

1. **Use API keys** over username/password
2. **Least privilege** — create a dedicated user with only the roles the tools need
3. **HTTPS** for the gateway URL in production; only disable `SSL_VERIFY` in dev
4. **Never commit `.env`** with real credentials — it's already in `.gitignore`
5. Keep `IGNITION_MCP_ENABLE_SCRIPT_EXECUTION` off unless you specifically need
   `run_gateway_script` and understand the risk of arbitrary code execution on the gateway

## Troubleshooting Configuration

### Authentication Failures

```bash
# Test API key manually
curl -H "X-Ignition-API-Token: your_key" http://gateway:8088/data/api/v1/gateway-info

# Test basic auth manually
curl -u username:password http://gateway:8088/data/api/v1/gateway-info
```

### Network Connectivity

```bash
curl http://gateway:8088/data/api/v1/gateway-info
nslookup gateway.example.com
```

### Getting Help

1. Check the [Troubleshooting Guide](troubleshooting.md)
2. Review the [Installation Guide](installation.md)
3. Open an issue on GitHub

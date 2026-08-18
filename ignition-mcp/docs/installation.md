# Installation Guide

This guide walks through installing and setting up the Ignition MCP Server.

## Prerequisites

Before installing, ensure you have:

- **Python 3.10 or higher** installed on your system
- **Ignition Gateway 8.3+** with REST API enabled
- Valid credentials for your Ignition Gateway (API key preferred, or username/password)
- Network access to your Ignition Gateway
- [uv](https://github.com/astral-sh/uv) (recommended) or `pip`

## Installation

### Using uv (Recommended)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/yourusername/ignition-mcp.git
cd ignition-mcp

# Install dependencies into a managed virtual environment
uv sync
```

### Using pip

```bash
git clone https://github.com/yourusername/ignition-mcp.git
cd ignition-mcp

python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install -e .
```

### Development Installation

For development work, include the `dev` dependency group (pytest, mypy, ruff):

```bash
uv sync --group dev
# or
pip install -e ".[dev]"
```

## Configuration Setup

### 1. Create Environment File

```bash
cp .env.example .env
```

### 2. Edit Configuration

Open `.env` and set your gateway connection details:

```bash
# Gateway connection settings
IGNITION_MCP_IGNITION_GATEWAY_URL=http://localhost:8088

# Preferred: API key auth (Config → Security → Users, Roles → [User] → API Keys)
IGNITION_MCP_IGNITION_API_KEY=your_api_key_here

# Or fall back to basic auth
IGNITION_MCP_IGNITION_USERNAME=admin
IGNITION_MCP_IGNITION_PASSWORD=password

# Server settings (only used for streamable-http transport)
IGNITION_MCP_SERVER_HOST=127.0.0.1
IGNITION_MCP_SERVER_PORT=8007
```

See [Configuration Guide](configuration.md) for the full list of options, including
the WebDev endpoints needed for tag values, alarms, historian, and script execution.

## Verification

### Test the Gateway Connection

```bash
uv run python -c "
import asyncio
from ignition_mcp.ignition_client import IgnitionClient

async def test():
    async with IgnitionClient() as client:
        info = await client.get_gateway_info()
        print('Connected:', info)

asyncio.run(test())
"
```

### Run the Unit Tests

```bash
uv run pytest tests/ -v
```

### Start the MCP Server

```bash
# Streamable HTTP — http://localhost:8007/mcp
uv run python mcp_server.py

# stdio (for Claude Desktop / manual subprocess testing)
uv run python mcp_server.py --transport stdio
```

## Integration with Claude Code

Claude Code picks up MCP servers from a `.mcp.json` file in the project root. This
repo already ships one configured for stdio transport:

```json
{
  "mcpServers": {
    "ignition-mcp": {
      "command": "uv",
      "args": ["run", "--no-sync", "python", "mcp_server.py", "--transport", "stdio"]
    }
  }
}
```

Restart Claude Code (or reload the project) after editing `.mcp.json` or `.env`.

## Integration with Claude Desktop

### 1. Locate Claude Desktop Config

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

### 2. Add MCP Server Configuration

```json
{
  "mcpServers": {
    "ignition-mcp": {
      "command": "uv",
      "args": ["run", "python", "mcp_server.py", "--transport", "stdio"],
      "cwd": "/path/to/ignition-mcp",
      "env": {
        "IGNITION_MCP_IGNITION_GATEWAY_URL": "http://localhost:8088",
        "IGNITION_MCP_IGNITION_API_KEY": "your_api_key"
      }
    }
  }
}
```

### 3. Restart Claude Desktop

Close and restart Claude Desktop to load the new MCP server.

## Alternative Installation: Docker

```bash
# Build image
docker build -t ignition-mcp .

# Run container (streamable HTTP on port 8007)
docker run -d \
  --name ignition-mcp \
  -p 8007:8007 \
  -e IGNITION_MCP_IGNITION_GATEWAY_URL=http://your-gateway:8088 \
  -e IGNITION_MCP_IGNITION_API_KEY=your_api_key \
  ignition-mcp
```

## Troubleshooting Installation

### Python Version Error

```bash
python --version   # should be 3.10+
```

### Module Import Errors

```bash
uv sync            # or: pip install -e .
```

### Connection Timeout

```bash
curl http://localhost:8088/data/api/v1/gateway-info
```

If this fails, check the gateway URL, that the REST API is enabled, and firewall rules.

### Getting Help

1. Check the [Troubleshooting Guide](troubleshooting.md)
2. Review the [Configuration Guide](configuration.md)
3. Open an issue on GitHub

## Next Steps

1. Read the [Configuration Guide](configuration.md) for the full settings reference
2. Explore [Usage Examples](examples.md)
3. Check the [API Reference](api-reference.md) for every tool's parameters
4. If you need tag values, alarms, historian, or script execution, follow
   [webdev-setup.md](webdev-setup.md) to deploy the required gateway-side scripts

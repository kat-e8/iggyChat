# ignition-mcp — How It Works

This document explains the project's file layout and the exact mechanics of how a
tool call travels from an AI client down to the Ignition Gateway and back.

## What this project is

`ignition-mcp` is a **Model Context Protocol (MCP) server** written in Python with
[FastMCP](https://github.com/jlowin/fastmcp). It exposes 37 tools that let an AI
assistant (Claude Code, Claude Desktop, or any MCP client) inspect and manage an
**Ignition Gateway** — projects, tag providers, tag values/config, alarms, tag
history, and gateway diagnostics — without the assistant needing to know Ignition's
REST API or scripting model directly.

It talks to the gateway over two completely different channels:

- **Native REST API** (`/data/api/v1/...`) — built into Ignition 8.3+, no extra
  setup required. Covers configuration-level data: gateway info, module health,
  logs, projects, project resources, designers, tag providers, and (as of the
  `database-connection`/`opc-connection` resource types) connection status.
- **WebDev module scripts** (`/system/webdev/...`) — custom Python scripts you
  must deploy yourself in the Designer. Required for anything the native REST API
  doesn't cover: live tag reads/writes, tag CRUD, UDTs, alarms, tag history, and
  arbitrary gateway script execution.

## Top-level layout

```
ignition-mcp/
├── mcp_server.py              # Entry point — builds the FastMCP app, owns the lifespan
├── pyproject.toml             # Dependencies, ruff/mypy/pytest config
├── run_server.sh              # Convenience wrapper: uv run python mcp_server.py
├── Dockerfile                 # python:3.11-slim image, non-root user, HTTP healthcheck
├── .env / .env.example        # IGNITION_MCP_-prefixed configuration
├── .mcp.json                  # How Claude Code launches this server (stdio, via uv)
├── src/ignition_mcp/          # The actual package (see below)
├── tests/                     # Unit + integration test suite
└── docs/                      # WebDev setup guide, API reference, troubleshooting, etc.
```

## `src/ignition_mcp/` — the package

```
src/ignition_mcp/
├── __init__.py           # __version__ = "0.1.0"
├── main.py                # `python -m ignition_mcp` entry, delegates to mcp_server.main()
├── config.py               # Settings — pydantic-settings, env prefix IGNITION_MCP_
├── ignition_client.py       # IgnitionClient — the only thing that speaks HTTP to the gateway
└── tools/
    ├── __init__.py         # register_all(mcp) — wires every tool module into FastMCP
    ├── gateway.py           # get_gateway_info, get_module_health, get_gateway_logs,
    │                        #   get_database_connections, get_opc_connections, get_system_metrics
    ├── projects.py          # list/get/create/delete/copy/rename/export/import_project
    ├── resources.py         # list/get/set/delete_project_resource (Perspective views, scripts, queries)
    ├── designers.py         # list_designers
    ├── tag_providers.py     # list/get/create/delete_tag_provider
    ├── tags.py              # browse_tags, read_tags, write_tag, tag config CRUD, UDT tools
    ├── alarms.py             # get_active_alarms, get_alarm_history, acknowledge_alarms
    ├── historian.py          # get_tag_history
    └── execution.py          # run_gateway_script (off by default)
```

Every tool module follows the exact same three-part shape:

1. A private `_client(ctx)` helper that pulls the shared `IgnitionClient` out of
   the FastMCP request context.
2. One `async def` per tool — thin wrapper that validates/shapes arguments
   (via `Annotated[..., Field(...)]` for MCP-visible parameter docs), calls the
   matching `IgnitionClient` method, and catches exceptions into
   `{"error": "..."}` so a failure is a normal tool result, not a crash.
3. A `register(mcp)` function that calls `mcp.tool()(fn)` for each tool in the
   module. `tools/__init__.py:register_all()` calls every module's `register()`
   once, at import time in `mcp_server.py`.

## Request lifecycle — from tool call to gateway and back

```
AI client (Claude)
   │  calls e.g. get_database_connections
   ▼
FastMCP tool dispatcher
   │  looks up ctx.request_context.lifespan_context["client"]
   ▼
tools/gateway.py:get_database_connections(ctx)
   │  await _client(ctx).get_database_connections()
   ▼
ignition_client.py:IgnitionClient.get_database_connections()
   │  await self._request("GET", "/data/api/v1/resources/list/ignition/database-connection")
   ▼
IgnitionClient._request()
   │  attaches auth header (API token or Basic), Accept: application/json
   │  httpx.AsyncClient.request(...) → resp.raise_for_status()
   │  parses JSON if content-type is application/json
   ▼
Ignition Gateway (http://localhost:8088)
```

Key mechanics:

- **One shared `IgnitionClient` per server process.** `mcp_server.py`'s
  `lifespan()` async context manager creates a single `IgnitionClient` (one
  `httpx.AsyncClient`) when the server starts, stores it in
  `{"client": client}`, and every tool call across every request reuses the same
  instance via `ctx.request_context.lifespan_context["client"]`. It's closed
  once, on server shutdown.
- **Auth is chosen automatically.** `IgnitionClient._auth_headers()` prefers the
  API token (`X-Ignition-API-Token` header) if `IGNITION_MCP_IGNITION_API_KEY` is
  set; otherwise it falls back to HTTP Basic auth built from
  `IGNITION_MCP_IGNITION_USERNAME`/`_PASSWORD`.
- **Errors never crash the tool call.** Every tool function wraps its client call
  in `try/except Exception` and returns `{"error": "..."}`, so a 404/500/timeout
  from the gateway comes back to the AI as readable JSON instead of failing the
  whole MCP request.
- **WebDev-backed tools gate on configuration first.** Tools like `read_tags` or
  `get_active_alarms` check a `webdev_*_configured` property (a simple `bool(...)`
  on the relevant `IGNITION_MCP_WEBDEV_*_ENDPOINT` setting) *before* trying the
  call, returning a structured "not configured" error with setup guidance if the
  endpoint isn't set.

## Two backends, one client class

`IgnitionClient` (in `ignition_client.py`) has one method per gateway operation,
grouped by backend:

**Native REST** — methods build a `/data/api/v1/...` path and call
`self._request()` directly. Examples: `get_gateway_info` →
`/data/api/v1/gateway-info`, `list_projects` → `/data/api/v1/projects/list`,
`browse_tags` → `/data/api/v1/entity/browse`, and the generic resource-type
listing pattern used by `list_tag_providers`, `get_database_connections`, and
`get_opc_connections`: `/data/api/v1/resources/list/{module}/{resource-type}`
(e.g. `ignition/tag-provider`, `ignition/database-connection`,
`ignition/opc-connection`).

**WebDev** — methods build a URL from a *configured resource path*, not a fixed
route: `_webdev_url()` / `_webdev_tag_config_url()` / `_webdev_alarm_url()` /
`_webdev_tag_history_url()` / `_webdev_script_exec_url()` each read their
respective `IGNITION_MCP_WEBDEV_*_ENDPOINT` setting and produce
`/system/webdev/{that path}`. The request body is always a JSON payload with an
`action` field (e.g. `{"action": "getActive", ...}`), because a single WebDev
resource multiplexes several operations via its `doPost` handler — see
`docs/webdev-setup.md` for the actual gateway-side Python each endpoint expects
(e.g. the `tags` endpoint dispatches on whether the body has `paths` (read) or
`tagPath` (write); `tagConfig`, `alarms`, and `scriptExec` dispatch on
`action`).

This is why WebDev tools require you to hand-deploy Jython scripts in the
Designer first (`docs/webdev-setup.md` has the exact code to paste into each
WebDev resource's `doPost`), while native-REST tools work out of the box against
any Ignition 8.3+ gateway.

## Configuration (`config.py`)

A single `pydantic-settings` `Settings` class, loaded once as the module-level
`settings` singleton. All fields read from environment variables prefixed
`IGNITION_MCP_`, with `.env` as a fallback file. Key fields:

| Field | Purpose |
|---|---|
| `ignition_gateway_url` | Base URL, e.g. `http://localhost:8088` |
| `ignition_api_key` / `ignition_username` / `ignition_password` | Auth — API key wins if set |
| `ssl_verify` | Set false for self-signed gateway certs |
| `webdev_tag_endpoint`, `webdev_tag_config_endpoint`, `webdev_alarm_endpoint`, `webdev_tag_history_endpoint`, `webdev_script_exec_endpoint` | Per-feature WebDev resource paths; empty = feature disabled |
| `enable_script_execution` | Hard off-switch for `run_gateway_script`, independent of whether its WebDev endpoint is configured |
| `server_host` / `server_port` | Bind address for `streamable-http` transport (default `127.0.0.1:8007`) |

## How the server actually starts

`mcp_server.py` is the single entry point (both `run_server.sh` and
`python -m ignition_mcp` funnel into its `main()`):

1. `sys.path` gets `src/` prepended so `ignition_mcp` is importable without
   installation.
2. `mcp = FastMCP("ignition-mcp", lifespan=lifespan)` is constructed at module
   level, then `register_all(mcp)` registers all 37 tools immediately — this
   happens once, at import time, regardless of transport.
3. `main()` parses `--transport` (`streamable-http` default, or `stdio`),
   `--host`, `--port`, and calls `mcp.run(...)` accordingly.

**Two ways this project runs in practice:**

- **stdio** (what `.mcp.json` uses for Claude Code): the MCP client spawns
  `uv run --no-sync python mcp_server.py --transport stdio` as a subprocess and
  talks to it over stdin/stdout. There's no network port — the process lives and
  dies with the client's connection to it. This is why editing the source code
  requires a client-side reconnect (`/mcp` → reconnect) to pick up changes: the
  old subprocess is still running the old code in memory until it's restarted.
- **streamable-http** (default, used by `run_server.sh` and the `Dockerfile`):
  binds `host:port` (`127.0.0.1:8007` locally, `0.0.0.0:8007` in the container)
  and serves the MCP protocol over HTTP at `/mcp`. Multiple clients could connect
  to the same running server.

## Tests (`tests/`)

- `test_client.py` — unit tests for `IgnitionClient` methods against a mocked
  `httpx.AsyncClient` (via the `mock_client`/`mock_httpx_response` fixtures in
  `conftest.py`). Asserts the right URL/method/payload is built for each method.
- `test_tools.py` — unit tests for the tool-layer functions in `tools/*.py`,
  mocking `IgnitionClient` itself to check argument shaping and error handling.
- `test_integration.py` — exercises tools against a *real* gateway; skipped
  unless `RUN_LIVE_GATEWAY_TESTS=1` is set.
- `conftest.py` also provides a `webdev_settings` fixture that monkeypatches all
  five WebDev endpoint settings to their conventional `Global/GatewayAPI/*`
  paths, for tests that need WebDev-backed tools to appear "configured".

## Known gap fixed in this session

The native-REST `get_database_connections`/`get_opc_connections` methods
originally called `/data/api/v1/connections/database` and
`/data/api/v1/connections/opc`, which 404 on Ignition 8.3.8 — those routes don't
exist. The correct routes follow the same generic resource-list pattern already
used by `list_tag_providers`:
`/data/api/v1/resources/list/ignition/database-connection` and
`/data/api/v1/resources/list/ignition/opc-connection`. Fixed in commit
`33bfc92`. Note there's a third, related concept not exposed by any tool yet:
OPC UA **device connections** (PLC drivers) live under a different resource type,
`/data/api/v1/resources/list/com.inductiveautomation.opcua/device` — distinct
from the `ignition/opc-connection` resource type, which is the OPC UA *server*
connection (e.g. the loopback connection to Ignition's own OPC UA server).

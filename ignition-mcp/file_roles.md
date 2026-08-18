# File Roles — What Every File in This Project Does

A high-level map of every tracked file in `ignition-mcp`, grouped by area.

## Entry points & runtime

| File | Role |
|---|---|
| `mcp_server.py` | The actual entry point. Builds the FastMCP app, defines the `lifespan` (creates one shared `IgnitionClient` for the process's whole life), registers all tools, and parses `--transport`/`--host`/`--port` to launch either `stdio` or `streamable-http`. |
| `src/ignition_mcp/main.py` | Thin `python -m ignition_mcp` shim — just imports and calls `mcp_server.main()`. Exists so the package is runnable as a module, not just a script. |
| `run_server.sh` | One-line convenience wrapper: `uv run python mcp_server.py "$@"` for the streamable-HTTP (default) launch path. |

## The package (`src/ignition_mcp/`)

| File | Role |
|---|---|
| `__init__.py` | Package marker, holds `__version__`. |
| `config.py` | The single `Settings` class (`pydantic-settings`). Defines every `IGNITION_MCP_*` environment variable, its default, and its description — this is the source of truth for configuration. |
| `ignition_client.py` | The only code that speaks HTTP to the gateway. One method per gateway operation, split into native-REST calls (build a `/data/api/v1/...` path) and WebDev calls (build a `/system/webdev/...` URL from a configured endpoint path). Owns auth header selection (API token vs Basic). |
| `tools/__init__.py` | `register_all(mcp)` — imports every tool module and calls its `register()` function once, wiring all 37 tools into the FastMCP instance. Also documents the full tool inventory in its docstring. |
| `tools/gateway.py` | 6 tools: gateway info, module health, logs, database/OPC connection status, system metrics. All native REST. |
| `tools/projects.py` | 8 tools: full project lifecycle — list/get/create/delete/copy/rename/export/import. Native REST. |
| `tools/resources.py` | 4 tools: read/write individual project resources (Perspective views, scripts, named queries) by path. Native REST. |
| `tools/designers.py` | 1 tool: list active Designer sessions. Native REST. |
| `tools/tag_providers.py` | 4 tools: list/get/create/delete tag providers (the containers tags live in). Native REST. |
| `tools/tags.py` | 9 tools: tag tree browsing (native REST) plus runtime read/write and full tag config CRUD, UDT inspection (all WebDev-backed). |
| `tools/alarms.py` | 3 tools: active alarms, alarm history, acknowledge. WebDev-backed. |
| `tools/historian.py` | 1 tool: query historical tag values. WebDev-backed. |
| `tools/execution.py` | 1 tool: `run_gateway_script` — arbitrary Python execution on the gateway. Off by default, gated by an explicit env flag; WebDev-backed. |

## Tests (`tests/`)

| File | Role |
|---|---|
| `__init__.py` | Package marker for the test suite. |
| `conftest.py` | Shared pytest fixtures — a mocked `httpx.Response` factory, a mocked `IgnitionClient`, and a fixture that patches all five WebDev endpoint settings to their conventional paths. |
| `test_client.py` | Unit tests for `IgnitionClient` — asserts each method builds the right URL/method/payload, against a mocked httpx client (no real gateway). |
| `test_tools.py` | Unit tests for the `tools/*.py` layer — mocks `IgnitionClient` itself, checks argument shaping, "not configured" error paths, and exception-to-`{"error": ...}` wrapping. |
| `test_integration.py` | Tests against a *real* gateway. Skipped unless `RUN_LIVE_GATEWAY_TESTS=1` is set. |

## Configuration & secrets

| File | Role |
|---|---|
| `.env` | Local, untracked (see `.gitignore`) actual values for every `IGNITION_MCP_*` setting — gateway URL, API token, WebDev endpoint paths. What the running server actually reads. |
| `.env.example` | Template for `.env` with every variable listed and commented, safe to commit — no real secrets. |
| `.mcp.json` | Tells Claude Code how to launch this server as an MCP tool provider for this project (stdio transport, `uv run` command). |
| `.mcp.json.example` | Shows the alternative `streamable-http` client config (connect to an already-running server by URL) instead of spawning a subprocess. |
| `pyproject.toml` | Package metadata, dependencies, and tool config in one place: `hatchling` build backend, `ruff` lint rules, `mypy` strictness, `pytest` settings (asyncio mode, test paths). |
| `uv.lock` | `uv`'s resolved, pinned dependency lockfile — guarantees everyone installs the exact same versions. |

## Docs (`docs/`)

| File | Role |
|---|---|
| `installation.md` | Prerequisites and setup steps (Python version, Ignition version, `uv` install, first run). |
| `configuration.md` | Full walkthrough of every environment variable and precedence rules (env var > `.env` > default). |
| `webdev-setup.md` | The gateway-side deployment guide — the actual Jython `doPost` scripts to paste into each WebDev resource (`tags`, `tagConfig`, `alarms`, `tagHistory`, `scriptExec`), plus security guidance for `run_gateway_script`. |
| `api-reference.md` | Full reference table of all 37 tools: name, transport (native REST vs WebDev), and description. |
| `examples.md` | Practical usage examples organized by feature area, written for someone driving the tools through Claude. |
| `troubleshooting.md` | Common failure modes and fixes — connection problems, auth errors, WebDev tool errors, Claude Code integration issues. |
| `contributing.md` | Dev setup, code style, testing, and PR process for anyone extending the server. |

## Session-generated documents (this repo root)

| File | Role |
|---|---|
| `ignition_mcp_mechanics.md` | Deep-dive on this server's own architecture and request lifecycle, written by tracing the source code directly. |
| `ignition-mcp.md` | Chronological summary of every query run in an earlier session, the components involved, and the bugs found/fixed along the way. |
| `ignition_logs.log` | A compiled snapshot of gateway log entries from a specific one-hour window, pulled via `get_gateway_logs` and annotated. |
| `ignition-mcp-workflow.pptx` | A slide deck explaining the same architecture — components, MCP protocol, and two worked request traces — built programmatically with `python-pptx`. |
| `file_roles.md` | This file. |

## Deployment & CI

| File | Role |
|---|---|
| `Dockerfile` | `python:3.11-slim` image, installs the package, runs as a non-root user, exposes port 8007, HTTP healthcheck against `/mcp`. Default command runs the streamable-HTTP transport. |
| `.dockerignore` | Excludes git metadata, caches, docs, and dev-only files from the Docker build context. |
| `.github/workflows/ci.yml` | On every push/PR: matrix-tests across Python 3.10–3.12 (ruff lint + format check, mypy, pytest), plus a separate job running `bandit` and `safety` for security/dependency scanning. |
| `.github/workflows/release.yml` | On a `v*` tag push: builds and pushes a multi-arch (amd64/arm64) Docker image to `ghcr.io`, then creates a GitHub Release with auto-generated notes. |

## Misc / tooling

| File | Role |
|---|---|
| `README.md` | The project's front door — what it is, the 37-tool inventory by category, setup, running instructions, WebDev prerequisites, architecture map, testing. |
| `LICENSE` | MIT license text. |
| `.gitignore` | Standard Python/IDE/OS ignore patterns, plus project-specific entries (env files, caches). |
| `.ralphrc` | Configuration for [Ralph](https://github.com/frankbria/ralph-claude-code), an autonomous-loop runner for Claude Code — call-rate limits, allowed tools, session continuity, and circuit-breaker thresholds for unattended runs. |
| `.claude/settings.local.json` | Local, personal Claude Code permission settings for this project — pre-approved Bash command prefixes and MCP tools that don't need a prompt each time, plus which `.mcp.json` servers are enabled. |

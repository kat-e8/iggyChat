"""Wires the Claude Agent SDK to two independent gateways:

- the shared Ignition MCP gateway (see Deployment/Phase10_*.pdf) -- iggyChat
  doesn't run one of its own, streamable-HTTP straight to the shared server,
  gated by the X-API-Key header held here rather than passed to the browser.
- the Generic Gateway (ManPage/api) -- docker-mcp, git-mcp, postgres-mcp,
  coder-commands-mcp, behind its own separate key.

Which of these a given ChatSession actually connects to is controlled by
`scope` -- see SCOPES and build_options() below. Scope is fixed at
ChatSession construction and can't change mid-session: widening/narrowing
access means opening a new WebSocket (see app.py), never mutating one that's
already running.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import asdict, is_dataclass
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from . import usage_store
from .config import settings

logger = logging.getLogger("chat_bridge.claude")


def _mcp_servers() -> dict[str, dict[str, Any]]:
    generic_headers = {"X-API-Key": settings.generic_gateway_api_key}
    return {
        "ignition": {
            "type": "http",
            "url": settings.ignition_mcp_url,
            "headers": {"X-API-Key": settings.ignition_mcp_api_key},
        },
        # ManPage/api's proxy route is "/docker-mcp{path:path}" -> upstream
        # "/mcp{path}" -- the mount's own bare path (no extra /mcp suffix) is
        # what maps path="" -> upstream "/mcp". Confirmed directly against
        # the live gateway: {mount}/mcp is a 404, {mount} alone is a 200.
        "docker": {
            "type": "http",
            "url": f"{settings.generic_gateway_url}/docker-mcp",
            "headers": generic_headers,
        },
        "git": {
            "type": "http",
            "url": f"{settings.generic_gateway_url}/git-mcp",
            "headers": generic_headers,
        },
        "postgres": {
            "type": "http",
            "url": f"{settings.generic_gateway_url}/postgres-mcp",
            "headers": generic_headers,
        },
        "coder_commands": {
            "type": "http",
            "url": f"{settings.generic_gateway_url}/coder-commands-mcp",
            "headers": generic_headers,
        },
    }


# Which servers (keys of _mcp_servers()) a session gets, by scope. Ignition is
# the default/narrowest scope; "generic" and "all" are explicit, user-chosen
# widenings picked via the Angular scope picker before a session opens (see
# app.py's websocket handler and frontend chat-scope-picker.ts).
SCOPES: dict[str, list[str]] = {
    "ignition": ["ignition"],
    "generic": ["docker", "git", "postgres", "coder_commands"],
    "all": ["ignition", "docker", "git", "postgres", "coder_commands"],
}
DEFAULT_SCOPE = "ignition"


def _system_prompt(servers: dict[str, dict[str, Any]]) -> str:
    if "ignition" not in servers:
        # Generic-only session: no Ignition tools are connected, so the
        # gateway_url/api_key override instructions below would be actively
        # wrong (there's nothing for them to apply to).
        return "You are the assistant for this app. Answer using the connected mcp__* tools only."

    # The shared Ignition gateway serves multiple consumers and defaults to a
    # dev Ignition instance -- every mcp__ignition__* tool call must
    # explicitly override gateway_url/api_key to reach one of this app's own
    # named targets, or the call fails with "Failed to reach gateway" against
    # the wrong instance. Confirmed by testing: omitting the override
    # reproduces exactly that error. Still required in the "all" scope, since
    # Ignition tools are connected there too.
    ignition_override = (
        "On every call to an mcp__ignition__* tool, you must explicitly "
        "pass gateway_url and api_key -- the tool "
        "server's own default target is a different, unrelated Ignition "
        "instance. Two named targets are available:\n"
        f'- "ignition-prod": gateway_url="{settings.ignition_target_gateway_url}", '
        f'api_key="{settings.ignition_target_api_key}"\n'
        f'- "ignition-dev": gateway_url="{settings.ignition_dev_gateway_url}", '
        f'api_key="{settings.ignition_dev_api_key}"\n'
        "Use ignition-dev unless the user explicitly asks for the prod "
        'gateway (e.g. "ignition-prod", "the prod instance", "production") '
        "for that turn.\n\n"
        "mcp__ignition__edit_tags / create_tags path pitfall: passing a "
        "nested tag as a flat 'name' (e.g. name=\"Folder/Tag\") or as a "
        "'path' field does NOT address the existing nested tag -- it "
        "silently creates a new, unrelated tag at the provider root "
        "instead, leaving the real tag unchanged. Confirmed by direct "
        "testing against this same tool. To edit a tag inside a folder, "
        "nest it the way Ignition's own tag export JSON does: wrap it in "
        "its parent folder object(s), e.g. to edit [default]Ramp/Ramp1:\n"
        '  {"name": "Ramp", "tagType": "Folder", "tags": '
        '[{"name": "Ramp1", "historyEnabled": true, "historyProvider": "DB"}]}\n'
        "After every edit_tags/create_tags call that targets a nested tag, "
        "verify the change actually landed by calling get_tag_config on the "
        "exact target path and confirming the fields you set are present. "
        "Also browse_tags the provider root once to confirm no stray "
        "sibling tag was created there. If verification shows the wrong "
        "tag was created or the target tag is unchanged, do not report "
        "success -- retry with the corrected nested structure, and only "
        "report the operation as done once verification passes."
    )
    if len(servers) == 1:
        # A plain string (not a preset) means this session skips the full
        # Claude Code system prompt entirely -- this app is a narrow
        # Ignition assistant, not a coding agent, and the smaller prompt is
        # less per-turn token overhead (see Phase7's cost findings). Only
        # true for the ignition-only scope; "all" below needs the fuller
        # prompt since it's not narrowly Ignition-only anymore.
        return f"You are the Ignition assistant for this app. Answer using the mcp__ignition__* tools only. {ignition_override}"
    return (
        "You are the assistant for this app, with access to both Ignition "
        "tools and generic infrastructure tools (docker, git, postgres, "
        f"coder commands). {ignition_override}"
    )


def build_options(scope: str = DEFAULT_SCOPE) -> ClaudeAgentOptions:
    servers = {name: spec for name, spec in _mcp_servers().items() if name in SCOPES[scope]}
    return ClaudeAgentOptions(
        system_prompt=_system_prompt(servers),
        mcp_servers=servers,
        # tools=[] disables every built-in Claude Code tool (Bash, Read,
        # Write, Edit, Grep, WebFetch, ...) -- without this, a chat user gets
        # those tools too (running against the Bridge's own host/cwd)
        # whenever an MCP tool isn't available or relevant, since
        # allowed_tools only auto-approves tools, it doesn't restrict which
        # ones exist. Confirmed by edge-case testing: with the Gateway down,
        # Claude fell back to Bash/Grep against the Bridge's filesystem.
        tools=[],
        # Ignore any .mcp.json / global MCP config the `claude` subprocess
        # might otherwise pick up -- only the servers selected by scope above
        # are ever available.
        strict_mcp_config=True,
        # Auto-approve every server actually connected for this scope --
        # there's no interactive terminal on the other end of this
        # connection to answer a permission prompt. Servers outside
        # `servers` above have no tools to approve in the first place: this
        # can only widen *within* what scope already connected, never reach
        # a server scope left out. Per-tool confirmation UX for high-impact
        # actions is an open question from mcp_frontend_v3.pdf, not yet
        # resolved.
        allowed_tools=[f"mcp__{name}__*" for name in servers],
        model=settings.claude_model,
        # Secondary safety net beneath the cumulative daily cap in app.py --
        # this one's per-session (per WebSocket connection) and enforced by
        # the SDK itself, so a single runaway conversation can't blow past
        # it even if the daily total is still under budget. None disables it.
        max_budget_usd=settings.max_session_budget_usd,
    )


def _serialize_block(block: Any) -> dict[str, Any]:
    if isinstance(block, TextBlock):
        return {"type": "text", "text": block.text}
    if isinstance(block, ToolUseBlock):
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    if isinstance(block, ToolResultBlock):
        return {
            "type": "tool_result",
            "tool_use_id": block.tool_use_id,
            "content": [_serialize_block(b) for b in block.content],
        }
    if isinstance(block, ThinkingBlock):
        return {"type": "thinking", "thinking": block.thinking}
    return {"type": type(block).__name__}


def serialize_message(message: Any) -> dict[str, Any]:
    if isinstance(message, AssistantMessage):
        return {"type": "assistant", "content": [_serialize_block(b) for b in message.content]}
    if isinstance(message, UserMessage):
        return {"type": "user", "content": [_serialize_block(b) for b in message.content]}
    # SystemMessage/ResultMessage/StreamEvent/etc: exact field shapes vary by
    # SDK version, so fall back to a generic dataclass dump rather than
    # guessing field names.
    if is_dataclass(message) and not isinstance(message, type):
        return {"type": type(message).__name__, **asdict(message)}
    return {"type": type(message).__name__}


class ChatSession:
    """Wraps one ClaudeSDKClient for the lifetime of a single chat WebSocket connection.

    scope is fixed at construction and there is no method to change it later --
    that's deliberate. Changing scope means opening a new WebSocket (and thus a
    new ChatSession), never mutating one mid-conversation.
    """

    def __init__(self, scope: str = DEFAULT_SCOPE) -> None:
        self.scope = scope
        self._client = ClaudeSDKClient(options=build_options(scope))

    async def __aenter__(self) -> "ChatSession":
        await self._client.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._client.disconnect()

    async def send(self, prompt: str) -> AsyncIterator[dict[str, Any]]:
        await self._client.query(prompt)
        async for message in self._client.receive_response():
            if isinstance(message, ResultMessage):
                await _record_turn_cost(message)
            yield serialize_message(message)


async def _record_turn_cost(message: ResultMessage) -> None:
    """Logs and persists per-turn model/cache/cost data the SDK already computes.

    Added to diagnose real-world API-key billing burning through credit much
    faster than expected -- canonicalModel answers "which model actually
    ran" and cacheReadInputTokens vs. cacheCreationInputTokens/inputTokens
    answers "is prompt caching hitting", per turn, without guessing. Also
    feeds usage_store, which backs the cumulative daily budget cap.
    """
    if message.total_cost_usd is not None:
        logger.info("turn total: $%.4f session=%s", message.total_cost_usd, message.session_id)
    for model_key, usage in (message.model_usage or {}).items():
        logger.info(
            "  model=%s canonical=%s provider=%s in=%d cache_read=%d cache_write=%d out=%d cost=$%.4f",
            model_key,
            usage.get("canonicalModel", "?"),
            usage.get("provider", "?"),
            usage.get("inputTokens", 0),
            usage.get("cacheReadInputTokens", 0),
            usage.get("cacheCreationInputTokens", 0),
            usage.get("outputTokens", 0),
            usage.get("costUSD", 0.0),
        )
        # sqlite3 is blocking -- keep it off the event loop so one client's
        # write doesn't stall every other connected WebSocket.
        await asyncio.to_thread(usage_store.record_usage, message.session_id, model_key, usage)

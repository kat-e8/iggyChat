"""Wires the Claude Agent SDK to two independent gateways:

- the shared Ignition MCP gateway (see Deployment/Phase10_*.pdf) -- Rosetta
  doesn't run one of its own, streamable-HTTP straight to the shared server,
  gated by the X-API-Key header held here rather than passed to the browser.
  Which Ignition gateway it reaches is chosen per call, from the named
  targets in config (see _system_prompt).
- the Canary Gateway (Canary Labs Historian MCP) -- a single unauthenticated
  endpoint.

Each is its own scope and a session only ever connects one of them. Ignition
and Canary both have "tags", so keeping them apart is what stops an Ignition
question from being answered out of the Historian or the other way round.

Which of these a given ChatSession actually connects to is controlled by
`scope` -- see SCOPES and build_options() below. A session's scope can
change mid-session via ChatSession.switch_scope(), which reconnects the SDK
client with a different mcp_servers set while resuming the same underlying
Claude conversation (see app.py's websocket handler).
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
    return {
        "ignition": {
            "type": "http",
            "url": settings.ignition_mcp_url,
            "headers": {"X-API-Key": settings.ignition_mcp_api_key},
        },
        # Canary Gateway -- no headers: this endpoint has no API-key auth at
        # all (see config.py's canary_gateway_url comment).
        "canary": {
            "type": "http",
            "url": settings.canary_gateway_url,
        },
    }


# Which servers (keys of _mcp_servers()) a session gets, by scope. One server
# per scope, never both: with only one connected, the other system's tools
# don't exist for that session (see build_options' strict_mcp_config), so the
# dropdown choice is a hard boundary, not a hint. Selectable at session start
# or mid-session via the Angular scope dropdown (see app.py's websocket
# handler and frontend chat-scope-select.ts).
SCOPES: dict[str, list[str]] = {
    "ignition": ["ignition"],
    "canary": ["canary"],
}
DEFAULT_SCOPE = "ignition"


# Both systems call their data points "tags", so each scope's prompt says
# whose tags this conversation means and turns the other system's questions
# away rather than answering them from the wrong source.
_IGNITION_ROLE = (
    "You are the Ignition assistant for this app. Answer using the "
    "mcp__ignition__* tools only. In this conversation, \"tags\" always means "
    "Ignition gateway tags. If the user asks about Canary Historian data, say "
    "that belongs in the Canary scope (the dropdown above the chat) instead of "
    "answering it here."
)
_CANARY_ROLE = (
    "You are the Canary Historian assistant for this app. Answer using the "
    "mcp__canary__* tools only. In this conversation, \"tags\" always means "
    "Canary Historian tags. If the user asks about an Ignition gateway's tags, "
    "configuration or alarms, say that belongs in the Ignition scope (the "
    "dropdown above the chat) instead of answering it here."
)


def _ignition_targets() -> str:
    # The shared Ignition MCP gateway is multi-tenant and its own default
    # target is an unrelated instance -- every mcp__ignition__* call must pass
    # gateway_url/api_key explicitly or it fails with "Failed to reach
    # gateway" against the wrong one. Confirmed by testing: omitting the
    # override reproduces exactly that error. The names, URLs and default all
    # come from config (IGNITION_TARGETS / IGNITION_DEFAULT_TARGET).
    listed = "\n".join(
        f'- "{name}": gateway_url="{target.gateway_url}", api_key="{target.api_key}"'
        for name, target in settings.ignition_targets.items()
    )
    return (
        "On every call to an mcp__ignition__* tool, you must explicitly pass "
        "gateway_url and api_key for one of these named Ignition gateways -- "
        "the tool server's own default target is a different, unrelated "
        f"instance:\n{listed}\n"
        f'Start on "{settings.ignition_default_target}". If the user names '
        "another gateway for one request, use it for that request only. If "
        'the user asks to switch (e.g. "use dev from now on"), use that '
        "gateway for every later call in this conversation until they switch "
        "again, and say which gateway you are now using. If the user names a "
        "gateway that is not in this list, say so and list the available "
        "names -- never guess or construct a gateway_url yourself."
    )


# Canary needs no target list here: canary-mcp-gateway holds each Historian's
# connection (and its API token) itself, and every tool takes an optional
# `connection` alias that falls back to the gateway's own default. Which
# Historians exist, and which is the default, is gateway config.
_CANARY_TARGETS = (
    "Every mcp__canary__* tool takes an optional `connection` argument naming "
    "which Canary Historian to use; leaving it out uses the default Historian. "
    "If the user asks for a different Historian, call list_connections to see "
    "which aliases exist. If the user names another Historian for one "
    "request, pass it for that request only. If the user asks to switch, "
    "pass that alias as `connection` on every later call in this conversation "
    "until they switch again, and say which Historian you are now using. If "
    "the name they give is not one of the aliases, say so and list them."
)


_IGNITION_TAG_EDITING = (
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


def _system_prompt(scope: str) -> str:
    # A plain string (not a preset) means this session skips the full Claude
    # Code system prompt entirely -- this app is a narrow assistant, not a
    # coding agent, and the smaller prompt is less per-turn token overhead
    # (see Phase7's cost findings).
    if scope == "canary":
        return f"{_CANARY_ROLE}\n\n{_CANARY_TARGETS}"
    return f"{_IGNITION_ROLE}\n\n{_ignition_targets()}\n\n{_IGNITION_TAG_EDITING}"


def build_options(scope: str = DEFAULT_SCOPE, resume: str | None = None) -> ClaudeAgentOptions:
    servers = {name: spec for name, spec in _mcp_servers().items() if name in SCOPES[scope]}
    return ClaudeAgentOptions(
        # Set when switching scope mid-conversation (see ChatSession.switch_scope)
        # so the underlying Claude session's history carries over -- only the
        # connected MCP servers change, not the conversation itself.
        resume=resume,
        system_prompt=_system_prompt(scope),
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

    scope can change mid-conversation via switch_scope() -- see there for how
    conversation continuity survives that despite the underlying
    ClaudeSDKClient being torn down and rebuilt.
    """

    def __init__(self, scope: str = DEFAULT_SCOPE) -> None:
        self.scope = scope
        self._session_id: str | None = None
        self._client = ClaudeSDKClient(options=build_options(scope))

    async def __aenter__(self) -> "ChatSession":
        await self._client.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._client.disconnect()

    async def send(self, prompt: str) -> AsyncIterator[dict[str, Any]]:
        await self._client.query(prompt)
        async for message in self._client.receive_response():
            session_id = getattr(message, "session_id", None)
            if session_id:
                self._session_id = session_id
            if isinstance(message, ResultMessage):
                await _record_turn_cost(message)
            yield serialize_message(message)

    async def switch_scope(self, scope: str) -> None:
        """Swap which MCP servers/tools this session has connected, without
        losing the conversation: the old ClaudeSDKClient is disconnected and a
        new one built for the new scope, but passed `resume=self._session_id`
        so the same underlying Claude conversation continues -- only the
        connected tools change, not the message history.

        No-ops (still safe to call) if no turn has happened yet -- resume=None
        is just build_options()'s normal fresh-session behavior.
        """
        if scope == self.scope:
            return
        await self._client.disconnect()
        self.scope = scope
        self._client = ClaudeSDKClient(options=build_options(scope, resume=self._session_id))
        await self._client.connect()


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

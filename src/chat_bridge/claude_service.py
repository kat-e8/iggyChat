"""Wires the Claude Agent SDK to the MCP Gateway's /docker and /ignition sub-apps.

Each server is mounted by the Gateway as streamable-HTTP at <mount>/mcp (see
backend/mcp-gateway/src/gateway/app.py), gated by the X-API-Key header held
here rather than passed to the browser.
"""

from collections.abc import AsyncIterator
from dataclasses import asdict, is_dataclass
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from .config import settings


def _mcp_servers() -> dict[str, dict[str, Any]]:
    headers = {"X-API-Key": settings.gateway_api_key}
    return {
        "docker": {
            "type": "http",
            "url": f"{settings.gateway_url}/docker/mcp",
            "headers": headers,
        },
        "ignition": {
            "type": "http",
            "url": f"{settings.gateway_url}/ignition/mcp",
            "headers": headers,
        },
    }


def build_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        mcp_servers=_mcp_servers(),
        # tools=[] disables every built-in Claude Code tool (Bash, Read,
        # Write, Edit, Grep, WebFetch, ...) -- without this, a chat user gets
        # those tools too (running against the Bridge's own host/cwd)
        # whenever an MCP tool isn't available or relevant, since
        # allowed_tools only auto-approves tools, it doesn't restrict which
        # ones exist. Confirmed by edge-case testing: with the Gateway down,
        # Claude fell back to Bash/Grep against the Bridge's filesystem.
        tools=[],
        # Ignore any .mcp.json / global MCP config the `claude` subprocess
        # might otherwise pick up -- only the two servers below are ever
        # available.
        strict_mcp_config=True,
        # Auto-approve both tool servers -- there's no interactive terminal on
        # the other end of this connection to answer a permission prompt.
        # Per-tool confirmation UX for high-impact actions is an open
        # question from mcp_frontend_v3.pdf, not yet resolved.
        allowed_tools=["mcp__docker__*", "mcp__ignition__*"],
        model=settings.claude_model,
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
    """Wraps one ClaudeSDKClient for the lifetime of a single chat WebSocket connection."""

    def __init__(self) -> None:
        self._client = ClaudeSDKClient(options=build_options())

    async def __aenter__(self) -> "ChatSession":
        await self._client.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._client.disconnect()

    async def send(self, prompt: str) -> AsyncIterator[dict[str, Any]]:
        await self._client.query(prompt)
        async for message in self._client.receive_response():
            yield serialize_message(message)

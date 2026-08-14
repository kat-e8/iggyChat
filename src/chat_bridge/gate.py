"""Keeps chat requests scoped to what the MCP tools can actually answer, so
an off-topic prompt never reaches a full, tool-enabled turn against
GATEWAY_URL's ignition/docker MCP servers -- the expensive, credit-consuming
path.

Two stages, cheapest first:

1. Keyword filter (free): built from the vocabulary of the tools actually
   exposed by ignition-mcp and docker-mcp (see backend/ignition/ignition-mcp
   and backend/docker-mcp). No match -> rejected before any API call happens.
2. Tool router (cheap): prompts that pass stage 1 go through a single,
   tool-free Haiku classification call -- far cheaper than the real
   Sonnet/Opus turn with tool schemas and multi-step reasoning -- which makes
   the actual accept/reject call.
"""

import logging
import string

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

logger = logging.getLogger("chat_bridge.gate")

# Derived from the tool names/descriptions ignition-mcp and docker-mcp
# actually expose, plus the SCADA/process nouns those tools operate on. Keep
# in sync if either tool surface changes.
_KEYWORDS = {
    # Ignition / SCADA domain
    "tag", "tags", "alarm", "alarms", "alarming", "gateway", "gateways",
    "ignition", "opc", "opc-ua", "opcua", "plc", "plcs", "scada", "hmi",
    "historian", "history", "udt", "udts", "provider", "providers",
    "designer", "designers", "project", "projects", "resource", "resources",
    "database", "db", "connection", "connections", "script", "scripting",
    "module", "modules", "metric", "metrics", "log", "logs", "system",
    "boiler", "pump", "sensor", "sensors", "valve", "temperature",
    "pressure", "flow", "setpoint", "process", "acknowledge", "shelve",
    # Docker domain
    "docker", "container", "containers", "compose", "image", "images",
    "deploy", "deployment", "stack",
}


def passes_keyword_filter(prompt: str) -> bool:
    """Cheap, zero-API-call first pass -- rejects only when *nothing* in the
    prompt hints at the Ignition/Docker domain. Deliberately permissive
    (a single matching word is enough) since stage 2 does the real judgment
    call; this stage exists purely to catch obviously unrelated prompts for
    free.
    """
    words = {w.strip(string.punctuation).lower() for w in prompt.split()}
    return not words.isdisjoint(_KEYWORDS)


_ROUTER_SYSTEM_PROMPT = """\
You are a strict routing filter in front of a SCADA/industrial-automation \
assistant. The assistant can ONLY act through two tool integrations:

- Ignition MCP: browsing/reading/writing tags, alarms, tag history, \
OPC-UA and database connections, gateway scripting, projects, UDTs.
- Docker MCP: listing/creating containers, deploying compose stacks, \
reading container logs.

Given the user's message, decide whether answering it would plausibly \
require calling one of those tools, or is a reasonable in-scope follow-up \
(e.g. "thanks", "what did you just find", "try that again"). Reply with \
exactly one word: YES or NO. Nothing else.
"""

# Short alias, consistent with CLAUDE_MODEL's own convention (see config.py)
# -- resolves to the current Haiku release rather than a pinned model ID.
_ROUTER_MODEL = "haiku"


async def passes_tool_router(prompt: str) -> bool:
    """Single tool-free Haiku call deciding whether `prompt` is plausibly
    answerable via the Ignition/Docker MCP tools. Fails open (allows the
    prompt through) if the router call itself errors, so an infra hiccup in
    this pre-filter doesn't take down chat entirely -- only the real turn's
    own error handling should ever surface to the user.
    """
    options = ClaudeAgentOptions(
        system_prompt=_ROUTER_SYSTEM_PROMPT,
        tools=[],
        mcp_servers={},
        strict_mcp_config=True,
        max_turns=1,
        model=_ROUTER_MODEL,
    )
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        return block.text.strip().upper().startswith("Y")
    except Exception:
        logger.exception("Tool router call failed; failing open for this prompt")
        return True
    return True


async def should_forward(prompt: str) -> bool:
    """True if `prompt` should be sent on to the real, tool-enabled turn."""
    if not passes_keyword_filter(prompt):
        return False
    return await passes_tool_router(prompt)

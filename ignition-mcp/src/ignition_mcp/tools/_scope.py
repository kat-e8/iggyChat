"""Shared per-call IgnitionClient scoping.

Lets any tool override the gateway URL / API key for a single call instead of
always using the server's configured default (loaded once at startup and
shared across all calls via the FastMCP lifespan).
"""

from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator, Optional, cast

from fastmcp import Context
from pydantic import Field

from ..ignition_client import IgnitionClient

GatewayUrlOverride = Annotated[
    Optional[str],
    Field(
        description=(
            "Override the Ignition Gateway base URL for this call only, e.g. "
            "'http://192.168.1.50:8088'. Omit to use the server's configured gateway."
        )
    ),
]

ApiKeyOverride = Annotated[
    Optional[str],
    Field(
        description=(
            "Override the Ignition Gateway API key for this call only. "
            "Omit to use the server's configured key."
        )
    ),
]


@asynccontextmanager
async def scoped_client(
    ctx: Context,
    gateway_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> AsyncIterator[IgnitionClient]:
    """Yield an IgnitionClient for this call.

    With no overrides, yields the shared client created once at server startup
    (owned by the FastMCP lifespan — not closed here). When gateway_url or
    api_key is given, creates a temporary client scoped to this call and closes
    it on exit, leaving the shared client untouched.
    """
    if gateway_url or api_key:
        client = IgnitionClient(gateway_url=gateway_url, api_key=api_key)
        try:
            yield client
        finally:
            await client.close()
        return

    if ctx.request_context is None:
        raise RuntimeError("Tool called outside of a request context")
    yield cast(IgnitionClient, ctx.request_context.lifespan_context["client"])

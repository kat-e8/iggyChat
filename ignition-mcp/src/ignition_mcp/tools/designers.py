"""Designer session tools."""

from typing import Any

from fastmcp import Context, FastMCP

from ._scope import ApiKeyOverride, GatewayUrlOverride, scoped_client


async def list_designers(
    ctx: Context,
    gateway_url: GatewayUrlOverride = None,
    api_key: ApiKeyOverride = None,
) -> Any:
    """List active Ignition Designer sessions.

    Shows who is connected to the Designer, which project they have open, and
    since when. Useful to check if anyone is actively editing before making
    programmatic changes to a project.
    """
    try:
        async with scoped_client(ctx, gateway_url, api_key) as client:
            return await client.list_designers()
    except Exception as exc:
        return {"error": f"Failed to list designers: {exc}"}


def register(mcp: FastMCP) -> None:
    """Register all designer tools with the FastMCP instance."""
    mcp.tool()(list_designers)

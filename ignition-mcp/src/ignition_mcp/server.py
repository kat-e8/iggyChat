"""FastMCP application construction for ignition-mcp.

Moved out of the root `mcp_server.py` script so the FastMCP instance is
importable from the installed `ignition_mcp` package (e.g. by a gateway
that mounts it as a sub-app), not just runnable as a standalone script.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from .ignition_client import IgnitionClient
from .tools import register_all

logger = logging.getLogger("ignition-mcp")


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncGenerator[dict, None]:
    """Create and share a single IgnitionClient across all tool calls."""
    client = IgnitionClient()
    logger.info("IgnitionClient initialised — %s", client.gateway_url)
    try:
        yield {"client": client}
    finally:
        await client.close()
        logger.info("IgnitionClient closed")


mcp = FastMCP("ignition-mcp", lifespan=lifespan)
register_all(mcp)

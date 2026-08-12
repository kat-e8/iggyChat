"""FastAPI gateway mounting docker-mcp and ignition-mcp as sub-apps.

Each mounted MCP server owns a Starlette sub-app with its own lifespan
(docker-mcp starts a StreamableHTTPSessionManager; ignition-mcp opens an
IgnitionClient). FastAPI/Starlette do NOT start a mounted sub-app's lifespan
automatically, so both are composed into this app's lifespan explicitly via
AsyncExitStack -- skipping this leaves the mounted routes returning 500s.
"""

from contextlib import AsyncExitStack, asynccontextmanager

from docker_mcp.server import create_streamable_http_app
from fastapi import FastAPI
from ignition_mcp.server import mcp as ignition_mcp

from .auth import APIKeyMiddleware
from .config import settings

docker_app = create_streamable_http_app()
ignition_app = ignition_mcp.http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(docker_app.router.lifespan_context(docker_app))
        await stack.enter_async_context(ignition_app.router.lifespan_context(ignition_app))
        yield


app = FastAPI(title="MCP Gateway", lifespan=lifespan)
app.add_middleware(APIKeyMiddleware, api_key=settings.api_key)
app.mount("/docker", docker_app)
app.mount("/ignition", ignition_app)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

"""API-key gate for the mounted MCP sub-apps.

Written as a raw ASGI middleware, not Starlette's BaseHTTPMiddleware --
BaseHTTPMiddleware buffers/wraps the response iterator, which is a known
source of trouble for long-lived streaming responses, and both mounted
sub-apps use SSE (streamable-http). This middleware only inspects the
request scope and otherwise passes scope/receive/send straight through
untouched, so it can't interfere with streaming.
"""

import hmac

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

PROTECTED_PREFIXES = ("/docker", "/ignition")


class APIKeyMiddleware:
    def __init__(self, app: ASGIApp, api_key: str) -> None:
        self.app = app
        self._api_key = api_key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(PROTECTED_PREFIXES):
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        provided = headers.get(b"x-api-key", b"").decode("latin-1")
        if not hmac.compare_digest(provided, self._api_key):
            response = JSONResponse({"detail": "Invalid or missing X-API-Key"}, status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

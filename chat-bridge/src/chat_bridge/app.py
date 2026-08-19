"""FastAPI entrypoint for the Chat Bridge.

/api/chat requires the JWT issued by /api/auth/login, carried as the
httpOnly `access_token` cookie -- the browser attaches it automatically to
the WebSocket upgrade request, so the Angular client never has to manage
the token itself.

Signup is closed -- there is no /api/auth/signup. Accounts are provisioned
by the operator via `docker exec ... python -m chat_bridge.manage_users
add <email>`, on top of the tailnet-only network access this app already
has. See Deployment/Phase8_*.pdf.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import usage_store
from .auth import authenticate_user, create_access_token, decode_access_token
from .claude_service import ChatSession
from .config import settings

logger = logging.getLogger("chat_bridge")

app = FastAPI(title="Chat Bridge")

ACCESS_TOKEN_COOKIE = "access_token"


class AuthRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _issue_token(email: str, response: Response) -> TokenResponse:
    token = create_access_token(email)
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return TokenResponse(access_token=token)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _require_auth(request: Request) -> str:
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    email = decode_access_token(token) if token else None
    if email is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return email


@app.get("/api/usage")
async def usage(request: Request) -> dict[str, Any]:
    _require_auth(request)
    return await asyncio.to_thread(usage_store.summary)


@app.post("/api/auth/login")
async def login(body: AuthRequest, response: Response) -> TokenResponse:
    if not authenticate_user(body.email, body.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _issue_token(body.email, response)


@app.websocket("/api/chat")
async def chat(websocket: WebSocket) -> None:
    token = websocket.cookies.get(ACCESS_TOKEN_COOKIE)
    email = decode_access_token(token) if token else None
    if email is None:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    try:
        async with ChatSession() as session:
            while True:
                raw = await websocket.receive_text()
                # Checked per message, not once at connect -- a long-lived
                # WebSocket session should keep seeing this on every message
                # once today's cumulative *estimated* spend (across every
                # session) crosses the configured threshold. This is a soft
                # heads-up, not a real spend cap: the SDK reports cost as if
                # metered per-token regardless of auth method, but this app
                # runs on a flat-rate subscription seat with no overage
                # billing, so there's no real money at stake -- don't block
                # the turn over it.
                if await asyncio.to_thread(usage_store.daily_budget_exceeded):
                    await websocket.send_json(
                        {
                            "type": "warning",
                            "warning": "daily_budget_exceeded",
                            "message": (
                                "Today's estimated Claude usage has crossed the "
                                "configured soft budget. This doesn't block "
                                "anything -- just a heads-up."
                            ),
                        }
                    )
                payload = json.loads(raw)
                prompt = payload.get("content", "")
                async for message in session.send(prompt):
                    await websocket.send_json(message)
    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected: %s", email)


# Registered last so /health and /api/* above always match first -- Starlette
# checks routes in registration order, and this mount's "/" prefix would
# otherwise swallow every request.
if settings.frontend_dist is not None and settings.frontend_dist.is_dir():
    frontend_dist = settings.frontend_dist
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    @app.exception_handler(404)
    async def spa_fallback(request: Request, exc: Exception) -> Response:
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return FileResponse(frontend_dist / "index.html")

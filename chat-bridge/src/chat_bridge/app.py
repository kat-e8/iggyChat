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
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import alias_store, usage_store
from .auth import authenticate_user, create_access_token, decode_access_token
from .claude_service import SCOPES, DEFAULT_SCOPE, ChatSession
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


class AliasCreate(BaseModel):
    # The name travels through the model as a tool argument, so keep it to a
    # plain, unambiguous shape: nothing that could read as a URL or as the
    # Canary gateway's "inline:" spec.
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    system: Literal["ignition", "canary"]
    url: str = Field(pattern=r"^https?://[^\s/]+(/[^\s]*)?$")
    api_key: str = Field(min_length=1)
    # Canary only: the Historian a write goes to. Reads don't need it.
    historian: str | None = None

    @field_validator("url")
    @classmethod
    def _no_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")


def _check_canary_url(body: AliasCreate) -> None:
    # A Canary alias is the Historian's base URL only -- the read/write API
    # ports and paths are added per call (see claude_service._resolve_alias).
    parts = urlsplit(body.url)
    if body.system == "canary" and (parts.port is not None or parts.path):
        raise HTTPException(
            status_code=422,
            detail="A Canary alias URL is the Historian's base URL only, e.g. https://canary-stage.stage.katlego.work "
            "(no port or path -- the API ports are added automatically).",
        )


# Aliases are shared by every signed-in user. Keys are write-only over HTTP:
# they come in on POST and are never returned (alias_store.list_aliases).
@app.get("/api/aliases")
async def list_aliases(request: Request) -> list[dict[str, Any]]:
    _require_auth(request)
    return await asyncio.to_thread(alias_store.list_aliases)


@app.post("/api/aliases", status_code=201)
async def create_alias(body: AliasCreate, request: Request) -> dict[str, str]:
    email = _require_auth(request)
    _check_canary_url(body)
    try:
        await asyncio.to_thread(
            alias_store.add_alias, body.name, body.system, body.url, body.api_key, body.historian, email
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    logger.info("Alias %s (%s -> %s) created by %s", body.name, body.system, body.url, email)
    return {"name": body.name}


@app.delete("/api/aliases/{name}", status_code=204)
async def delete_alias(name: str, request: Request) -> Response:
    email = _require_auth(request)
    if not await asyncio.to_thread(alias_store.remove_alias, name):
        raise HTTPException(status_code=404, detail=f"No such alias: {name}")
    logger.info("Alias %s deleted by %s", name, email)
    return Response(status_code=204)


@app.put("/api/aliases/{name}/default", status_code=204)
async def make_default_alias(name: str, request: Request) -> Response:
    email = _require_auth(request)
    if not await asyncio.to_thread(alias_store.set_default, name):
        raise HTTPException(status_code=404, detail=f"No such alias: {name}")
    logger.info("Alias %s made default by %s", name, email)
    return Response(status_code=204)


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

    # Initial scope, from the query string at connect time. Fail safe to the
    # default scope on anything missing or unrecognized, never to a scope the
    # user didn't pick. Can change later, mid-connection, via a "change_scope" message
    # below -- the WebSocket itself stays open across that, only the
    # underlying ChatSession's connected servers change (see switch_scope).
    requested_scope = websocket.query_params.get("scope")
    scope = requested_scope if requested_scope in SCOPES else DEFAULT_SCOPE

    await websocket.accept()
    # Echoed back so the Angular client renders its scope badge from what
    # Chat-Bridge actually applied, not from whatever it requested -- an
    # invalid/omitted scope that got defaulted is still shown correctly.
    await websocket.send_json({"type": "session_scope", "scope": scope})
    try:
        async with ChatSession(scope=scope) as session:
            while True:
                raw = await websocket.receive_text()
                payload = json.loads(raw)

                if payload.get("action") == "change_scope":
                    requested = payload.get("scope")
                    if requested in SCOPES:
                        await session.switch_scope(requested)
                    # Always re-confirm current scope, even for an invalid
                    # request or a no-op (already-selected) one -- keeps the
                    # client's badge/dropdown in sync with reality either way.
                    await websocket.send_json({"type": "session_scope", "scope": session.scope})
                    continue

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

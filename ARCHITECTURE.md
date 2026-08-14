# Chat Bridge — Architecture

This repo (`chat-bridge`) is a standalone backend-for-frontend (BFF): Python FastAPI + Claude Agent SDK, sitting between the Angular app (`../frontend`) and the existing MCP Gateway in `../backend/mcp-gateway`. It is the **only** backend the browser ever talks to — the MCP Gateway (`127.0.0.1:8000`, mounting `/docker` and `/ignition`, gated by an `X-API-Key` header) stays internal and is never reached directly by the browser.

## Ownership

Chat Bridge owns:
- `/api/auth/login`, `/api/auth/signup` — mock user (`test@angular-university.io` / `Angular123`), JWT issuance, no persistent DB for now
- `/api/chat` WebSocket, JWT-verified — runs `claude-agent-sdk`'s `ClaudeSDKClient`/`query()` per conversation, streams `SDKMessage` events back
- Holds the Gateway's `X-API-Key` server-side; MCP servers configured pointing at the Gateway's `/docker/mcp` and `/ignition/mcp` streamable-HTTP endpoints

The frontend project ships an empty Express skeleton (`../frontend/server/`) — deliberately **not used**. Its `proxy.conf.json` gets repointed from `:9000` to this Bridge's port so the frontend's "`/api` only" convention holds without Express in the path.

## Why

Documented in `../frontend/mcp_frontend_v3.pdf`, prepared 2026-08-13. v3 revised v2's plan against the real (already-scaffolded) Angular 22 signals/zoneless project, keeping the BFF architecture from v2 but reverting a v2-vs-Express detour — Express stays dormant, auth logic lives in the Bridge instead.

## Build order

The v3 plan's 10 steps are all done: bridge + MCP wiring, auth endpoints, JWT-gated WebSocket, frontend proxy repoint, Angular auth screens, ChatService + chat UI, routing + auth guard, end-to-end testing (including a real run against a live Ignition Gateway and MCP Gateway), edge-case testing, and deploy wiring. Don't introduce the frontend's Express skeleton into the request path unless this decision is explicitly reversed — if it is, the auth endpoints described here would need to move there instead.

## Resolved: JWT client storage

httpOnly cookie, set by `/api/auth/login` and `/api/auth/signup` (`auth.py`'s `create_access_token` + `app.py`'s `_issue_token`). The browser attaches it automatically to the `/api/chat` WebSocket upgrade request, so the Angular `AuthService` never has to read, store, or manually attach a token — it only needs to know login/signup succeeded. `/api/chat` reads the cookie via `websocket.cookies`, rejecting the handshake (`close(code=1008)`, before `accept()`) if it's missing or invalid.

## Security: built-in Claude Code tools are disabled

`claude_service.py`'s `build_options()` sets `tools=[]` and `strict_mcp_config=True`. Found by edge-case testing, not by design review: with the MCP Gateway unreachable, Claude fell back to running `Bash`/`Grep` **against the Bridge's own host filesystem**, because `allowed_tools` only auto-approves tools — it does not restrict which ones exist. Without `tools=[]`, every authenticated chat user effectively gets shell access on whatever machine runs the Bridge, since `ClaudeSDKClient` otherwise exposes the full Claude Code tool surface by default. `tools=[]` removes every built-in tool so only the two explicitly configured MCP servers (`docker`, `ignition`) are ever available; `strict_mcp_config=True` stops the `claude` subprocess from picking up any other `.mcp.json`/global MCP config. Don't remove either without a specific reason — this is load-bearing, not incidental hardening.

## Deploy

`Dockerfile` builds the Bridge alone (context is `chat-bridge/` itself). To also serve the Angular app from this same container — making the Bridge the single public entry point, per the plan — build the frontend first and copy its output into `chat-bridge/frontend-dist/` before `docker build` (see the Dockerfile's own header comment for the exact command); `config.py`'s `FRONTEND_DIST_PATH` then makes `app.py` mount it with SPA-route fallback to `index.html`, registered after every `/api/*` route so those always match first. Leave `frontend-dist/` absent (and `FRONTEND_DIST_PATH` unset) to run API-only, e.g. behind a separately hosted static build/CDN instead.

`../backend/mcp-gateway/docker-compose.yml` composes both services: `gateway` no longer publishes a port (`expose: 8000` only, reachable from `chat-bridge` at `http://gateway:8000` via compose's service-name DNS), `chat-bridge` publishes `8001` and is the only service reachable from the host — matching "only the Chat Bridge's port reaches the browser" from the plan.

## Open questions (not yet resolved)

- Whether the mock in-memory user model is permanent or a placeholder for real user storage later
- Per-tool confirmation UX for high-impact Docker/Ignition actions
- Whether conversation history should persist beyond a single WebSocket connection
- Session state doesn't survive a page reload (the auth guard checks a local signal, not the httpOnly cookie, since the cookie isn't readable from JS) — fixing this would need a session-check endpoint (e.g. `GET /api/auth/me`)

## Related conventions (frontend side)

The Angular app this Bridge serves requires all backend calls under `/api/*`, uses Signal Forms (not Reactive/template-driven), no RxJS on the client (native `WebSocket`/`fetch` wrapped as Promises), external template/style files only, and `OnPush`/signals/`inject()`-style components. Source: `../frontend/CLAUDE.md`, `../frontend/src/CLAUDE.md`, `../frontend/.claude/CLAUDE.md`.

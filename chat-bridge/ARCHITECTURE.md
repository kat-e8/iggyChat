# Chat Bridge — Architecture

This repo (`chat-bridge`) is a standalone backend-for-frontend (BFF): Python FastAPI + Claude Agent SDK, sitting between the Angular app (`../frontend`) and a shared MCP gateway running elsewhere on the host. It is the **only** backend the browser ever talks to. As of Phase 10 (see `Deployment/Phase10_*.pdf`), this project runs no gateway of its own — chat-bridge is an Ignition-specific frontend, and talks directly to a pre-existing, shared gateway (also used by other tools on the host) at `/ignition/mcp`, gated by an `X-API-Key` header.

## Ownership

Chat Bridge owns:
- `/api/auth/login` — permanent, SQLite-backed accounts (see `Deployment/Phase8_*.pdf`); signup is closed, accounts are provisioned by an operator CLI
- `/api/chat` WebSocket, JWT-verified — runs `claude-agent-sdk`'s `ClaudeSDKClient`/`query()` per conversation, streams `SDKMessage` events back
- Holds the shared gateway's `X-API-Key` server-side, plus the production Ignition gateway's own `gateway_url`/`api_key`, instructed via `system_prompt` on every `mcp__ignition__*` call (the shared gateway is multi-tenant and defaults to a different, unrelated Ignition instance)

The frontend project ships an empty Express skeleton (`../frontend/server/`) — deliberately **not used**. Its `proxy.conf.json` gets repointed from `:9000` to this Bridge's port so the frontend's "`/api` only" convention holds without Express in the path.

## Why

Documented in `../frontend/mcp_frontend_v3.pdf`, prepared 2026-08-13. v3 revised v2's plan against the real (already-scaffolded) Angular 22 signals/zoneless project, keeping the BFF architecture from v2 but reverting a v2-vs-Express detour — Express stays dormant, auth logic lives in the Bridge instead.

## Build order

Follow the v3 plan's step order: bridge + MCP wiring first, then auth endpoints, then JWT-gate the WebSocket, then frontend proxy repoint, then Angular auth/chat UI, then end-to-end + edge-case testing, then deploy. Don't introduce the frontend's Express skeleton into the request path unless this decision is explicitly reversed — if it is, the auth endpoints described here would need to move there instead.


## Open questions (not yet resolved)

- JWT client storage: httpOnly cookie set by the Bridge vs. token attached manually to the WS upgrade — this is the Bridge's call to make
- Whether the mock in-memory user model is permanent or a placeholder for real user storage later
- Per-tool confirmation UX for high-impact Docker/Ignition actions
- Whether conversation history should persist beyond a single WebSocket connection

## Related conventions (frontend side)

The Angular app this Bridge serves requires all backend calls under `/api/*`, uses Signal Forms (not Reactive/template-driven), no RxJS on the client (native `WebSocket`/`fetch` wrapped as Promises), external template/style files only, and `OnPush`/signals/`inject()`-style components. Source: `../frontend/CLAUDE.md`, `../frontend/src/CLAUDE.md`, `../frontend/.claude/CLAUDE.md`.

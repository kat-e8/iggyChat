# Build context is this directory (chat-bridge/):
#   docker build -t chat-bridge .
# (docker-compose.yml in backend/mcp-gateway/ sets this up for you.)
#
# To also serve the Angular app from this container (so the Bridge is the
# single public entry point -- see ARCHITECTURE.md), build the frontend and
# copy its output here BEFORE running `docker build`, from frontend/:
#   ng build && rm -rf ../chat-bridge/frontend-dist && cp -r dist/mcp-frontend/browser ../chat-bridge/frontend-dist
# If frontend-dist/ isn't present, the image just serves /api -- fine if the
# Angular build is hosted separately (static host/CDN) instead.

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /usr/local/bin/

WORKDIR /app
COPY . .
# Cache mount persists uv's downloaded-wheel cache across builds on the same
# host -- without it, every build re-downloads every dependency from
# scratch (including a ~90MB claude-agent-sdk wheel), which stalled badly on
# a slow network patch during Phase 4's first real CI run (see
# Deployment/Phase4_Build_Deploy_Workflows.pdf).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

EXPOSE 8001
ENV CHAT_BRIDGE_HOST=0.0.0.0
# Only takes effect if frontend-dist/ was populated before building (see
# above); otherwise this path doesn't exist and the Bridge serves /api only.
ENV FRONTEND_DIST_PATH=/app/frontend-dist

CMD ["uv", "run", "chat-bridge"]

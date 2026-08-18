# Build context must be the repo root (the parent of gateway/, docker-mcp/,
# and ignition-mcp/), because gateway's editable dependencies point at its
# sibling directories via relative paths. Build from the repo root:
#   docker build -f gateway/Dockerfile -t gateway .
# (docker-compose.yml at the repo root sets `context: .` for you.)

FROM python:3.12-slim

# docker-mcp shells out to the `docker` CLI (via python-on-whales for compose,
# and subprocess directly for the other tools) rather than speaking to the
# Engine API itself, so the CLI + compose plugin must be present in the image.
# The container talks to the HOST's Docker daemon over a mounted socket
# (Docker-outside-of-Docker) -- see the warning in docker-compose.yml about
# what that access grants.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /usr/local/bin/

WORKDIR /app
COPY docker-mcp ./docker-mcp
COPY ignition-mcp ./ignition-mcp
COPY gateway ./gateway

WORKDIR /app/gateway
RUN uv sync --locked --no-dev

EXPOSE 8000
ENV GATEWAY_HOST=0.0.0.0

CMD ["uv", "run", "gateway"]

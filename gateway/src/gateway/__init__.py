import argparse


def main() -> None:
    import uvicorn

    from .config import settings

    parser = argparse.ArgumentParser(description="MCP gateway (docker-mcp + ignition-mcp)")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    args = parser.parse_args()

    uvicorn.run("gateway.app:app", host=args.host, port=args.port)

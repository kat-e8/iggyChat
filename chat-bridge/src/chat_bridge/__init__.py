import uvicorn

from .config import settings


def main() -> None:
    uvicorn.run("chat_bridge.app:app", host=settings.host, port=settings.port)

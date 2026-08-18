import logging

import uvicorn

from .config import settings


def main() -> None:
    # Without this, every logger.info() call in this app (including the
    # pre-existing WebSocketDisconnect log in app.py) is silently dropped --
    # the root logger's default level is WARNING with no handler attached.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    uvicorn.run("chat_bridge.app:app", host=settings.host, port=settings.port)

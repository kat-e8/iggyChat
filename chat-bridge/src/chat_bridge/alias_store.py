"""SQLite-backed, shared store of named connection aliases.

An alias names one Ignition gateway or one Canary Historian -- its URL and
API key -- so a chat turn can say "on ign-stage, what tags exist?" and never
carry the key itself. Users create them at runtime through the Aliases form
(app.py's /api/aliases); every user sees and uses the same set.

Keys live only here and in the tool call the bridge rewrites just before it
runs (claude_service.py's alias hook): list_aliases() never returns them, so
neither the model nor the browser ever sees one.

Same pattern as user_store.py: a local SQLite file on the persistent
chat-bridge-data volume, so aliases survive container recreation.
"""

import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from .config import settings

SYSTEMS = ("ignition", "canary")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS aliases (
    name TEXT PRIMARY KEY,
    system TEXT NOT NULL CHECK (system IN ('ignition', 'canary')),
    url TEXT NOT NULL,
    api_key TEXT NOT NULL,
    historian TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_by TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


@dataclass(frozen=True)
class Alias:
    name: str
    system: str
    url: str
    api_key: str
    historian: str | None


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    path = settings.aliases_db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def list_aliases() -> list[dict[str, object]]:
    """Every alias, without its key -- the shape /api/aliases returns."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT name, system, url, historian, is_default, created_by, created_at "
            "FROM aliases ORDER BY system, name"
        ).fetchall()
    return [
        {
            "name": name,
            "system": system,
            "url": url,
            "historian": historian,
            "is_default": bool(is_default),
            "created_by": created_by,
            "created_at": created_at,
        }
        for name, system, url, historian, is_default, created_by, created_at in rows
    ]


def get_alias(name: str) -> Alias | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT name, system, url, api_key, historian FROM aliases WHERE name = ?", (name,)
        ).fetchone()
    return Alias(*row) if row else None


def default_alias(system: str) -> str | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT name FROM aliases WHERE system = ? AND is_default = 1", (system,)
        ).fetchone()
    return row[0] if row else None


def add_alias(name: str, system: str, url: str, api_key: str, historian: str | None, created_by: str) -> None:
    """Creates an alias. The first alias of a system becomes its default, so
    a fresh install needs no extra step before its first chat."""
    with _db() as conn:
        has_default = conn.execute(
            "SELECT 1 FROM aliases WHERE system = ? AND is_default = 1", (system,)
        ).fetchone()
        try:
            conn.execute(
                "INSERT INTO aliases (name, system, url, api_key, historian, is_default, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (name, system, url, api_key, historian, 0 if has_default else 1, created_by, time.time()),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Alias already exists: {name}") from exc


def remove_alias(name: str) -> bool:
    """Deletes an alias. If it was its system's default, the oldest remaining
    alias of that system takes over, so there is still somewhere to start."""
    with _db() as conn:
        row = conn.execute("SELECT system, is_default FROM aliases WHERE name = ?", (name,)).fetchone()
        if row is None:
            return False
        system, was_default = row
        conn.execute("DELETE FROM aliases WHERE name = ?", (name,))
        if was_default:
            conn.execute(
                "UPDATE aliases SET is_default = 1 WHERE name = "
                "(SELECT name FROM aliases WHERE system = ? ORDER BY created_at LIMIT 1)",
                (system,),
            )
        return True


def set_default(name: str) -> bool:
    """Makes `name` its system's default -- where new conversations start."""
    with _db() as conn:
        row = conn.execute("SELECT system FROM aliases WHERE name = ?", (name,)).fetchone()
        if row is None:
            return False
        conn.execute("UPDATE aliases SET is_default = (name = ?) WHERE system = ?", (name, row[0]))
        return True

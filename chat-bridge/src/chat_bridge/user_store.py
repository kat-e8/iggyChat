"""SQLite-backed, permanent user store.

Replaces auth.py's old in-memory dict, which was wiped every time the
process restarted -- meaning every redeploy silently deleted every
signed-up account (see Deployment/Phase7_Cost_Diagnostics_And_Usage_Guardrails.pdf).
Same pattern as usage_store.py: a local SQLite file, not a service, on the
same persistent chat-bridge-data volume so it survives container
recreation. A separate .db file from usage.db -- different concern, no
reason to couple their schemas or lifecycles.

Signup is closed (see Phase 8 report): there is no HTTP endpoint that
calls add_user. Accounts are provisioned by the operator via
manage_users.py, run with `docker exec`.
"""

import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager

from .config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""

# The frontend's reference screenshots imply this account -- seeded once so
# a fresh install still has something to log in with. INSERT OR IGNORE
# makes this safe to run on every startup: a no-op once the row exists,
# including after an operator has added real accounts. Hashing needs
# auth.py's PasswordHasher, so the caller passes the hash in rather than
# this module importing auth (which imports this module) and cycling.
_MOCK_EMAIL = "test@angular-university.io"


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    path = settings.users_db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def seed_mock_user_if_absent(password_hash: str) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (_MOCK_EMAIL, password_hash, time.time()),
        )


def get_password_hash(email: str) -> str | None:
    with _db() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE email = ?", (email,)).fetchone()
        return row[0] if row else None


def add_user(email: str, password_hash: str) -> None:
    with _db() as conn:
        try:
            conn.execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (email, password_hash, time.time()),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"User already exists: {email}") from exc


def remove_user(email: str) -> bool:
    """Deletes the account. Does NOT invalidate an already-issued JWT for
    it -- tokens are verified by signature/expiry only, not by re-checking
    the user store (see Phase 8 report, Known Limitation). A removed
    user's existing session can still work until their cookie expires."""
    with _db() as conn:
        cur = conn.execute("DELETE FROM users WHERE email = ?", (email,))
        return cur.rowcount > 0


def list_users() -> list[tuple[str, float]]:
    with _db() as conn:
        rows = conn.execute("SELECT email, created_at FROM users ORDER BY created_at").fetchall()
        return [(row[0], row[1]) for row in rows]

"""SQLite-backed cumulative Claude usage tracking.

A local file, not a service -- this app is single-instance, single-user
(see auth.py's mock user model), so anything heavier is unwarranted.
Backs the daily budget cap in app.py's WebSocket handler and the
GET /api/usage endpoint. All functions here are synchronous; callers in
async code paths should wrap them in asyncio.to_thread so a DB write
doesn't block the event loop for every other connected client.
"""

import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from .config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    session_id TEXT NOT NULL,
    model_key TEXT NOT NULL,
    canonical_model TEXT,
    input_tokens INTEGER NOT NULL,
    cache_read_tokens INTEGER NOT NULL,
    cache_creation_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_events_ts ON usage_events (ts);
"""


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    path = settings.usage_db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def record_usage(session_id: str, model_key: str, usage: dict[str, Any]) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO usage_events "
            "(ts, session_id, model_key, canonical_model, input_tokens, "
            " cache_read_tokens, cache_creation_tokens, output_tokens, cost_usd) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                time.time(),
                session_id,
                model_key,
                usage.get("canonicalModel"),
                usage.get("inputTokens", 0),
                usage.get("cacheReadInputTokens", 0),
                usage.get("cacheCreationInputTokens", 0),
                usage.get("outputTokens", 0),
                usage.get("costUSD", 0.0),
            ),
        )


def total_cost_since(cutoff_ts: float) -> float:
    with _db() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM usage_events WHERE ts >= ?",
            (cutoff_ts,),
        ).fetchone()
        return float(row[0])


def _utc_day_start(ts: float) -> float:
    # time.time() is UTC epoch seconds, so this is UTC-midnight -- fine for
    # a personal daily cap; not meant to align with the user's local day.
    return ts - (ts % 86400)


def daily_budget_exceeded() -> bool:
    if settings.max_daily_budget_usd is None:
        return False
    return total_cost_since(_utc_day_start(time.time())) >= settings.max_daily_budget_usd


def summary() -> dict[str, Any]:
    now = time.time()
    with _db() as conn:
        today_total = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM usage_events WHERE ts >= ?",
            (_utc_day_start(now),),
        ).fetchone()[0]
        all_time_total = conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM usage_events").fetchone()[0]
        by_model = conn.execute(
            "SELECT canonical_model, COUNT(*), SUM(cost_usd), "
            "SUM(input_tokens), SUM(cache_read_tokens), SUM(output_tokens) "
            "FROM usage_events GROUP BY canonical_model ORDER BY SUM(cost_usd) DESC"
        ).fetchall()
    return {
        "today_cost_usd": round(today_total, 4),
        "all_time_cost_usd": round(all_time_total, 4),
        "daily_budget_usd": settings.max_daily_budget_usd,
        "session_budget_usd": settings.max_session_budget_usd,
        "by_model": [
            {
                "model": row[0],
                "turns": row[1],
                "cost_usd": round(row[2], 4),
                "input_tokens": row[3],
                "cache_read_tokens": row[4],
                "output_tokens": row[5],
            }
            for row in by_model
        ],
    }

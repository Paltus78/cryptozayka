# cryptozayka/storage/pg.py
# -*- coding: utf-8 -*-
"""
PostgreSQL-storage layer — asyncpg-pool + batch / stats helpers.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Final, Optional

import asyncpg

from ..settings import get_settings

log = logging.getLogger(__name__)
_s = get_settings()

# ─────────────────────── DSN helper ───────────────────────────
def _dsn() -> str:
    """Settings.pg_dsn → PG_DSN env → POSTGRES_* env."""
    if getattr(_s, "pg_dsn", None):
        return _s.pg_dsn  # type: ignore[attr-defined]

    env_dsn = os.getenv("PG_DSN")
    if env_dsn:
        return env_dsn

    user = os.getenv("POSTGRES_USER", "zayka")
    pwd = os.getenv("POSTGRES_PASSWORD", "secret")
    db = os.getenv("POSTGRES_DB", "zayka")
    host = os.getenv("POSTGRES_HOST", "db")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"


# ─────────────────────── pool singleton ───────────────────────
_POOL: Optional[asyncpg.Pool] = None
_POOL_MIN: Final[int] = 1
_POOL_MAX: Final[int] = 5


async def get_pool() -> asyncpg.Pool:
    global _POOL
    if _POOL is None:
        log.info("Creating asyncpg pool → %s", _dsn())
        _POOL = await asyncpg.create_pool(
            _dsn(),
            min_size=_POOL_MIN,
            max_size=_POOL_MAX,
            timeout=15,
            command_timeout=60,
        )
        await _init_schema(_POOL)
        log.info("✅ asyncpg pool ready")
    return _POOL


# ─────────────────────── schema bootstrap ─────────────────────
_INIT_SQL = """
CREATE TABLE IF NOT EXISTS batches (
    id          SERIAL PRIMARY KEY,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    status      TEXT      NOT NULL DEFAULT 'new',         -- new|process|done|error
    payload     JSONB     NOT NULL,
    result      JSONB,
    error       TEXT
);

CREATE TABLE IF NOT EXISTS gpt_judgements (
    project  TEXT PRIMARY KEY,
    verdict  TEXT NOT NULL,
    text     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stats (
    metric TEXT PRIMARY KEY,
    value  BIGINT NOT NULL DEFAULT 0
);
"""


async def _init_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(_INIT_SQL)


# ───────────────────── batch helpers ──────────────────────────
async def add_batch(payload: list[dict[str, Any]]) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO batches (payload) VALUES ($1::jsonb) RETURNING id",
            json.dumps(payload),
        )
    return int(row["id"])


async def next_batch() -> tuple[int | None, str | None]:
    """
    Атомарно берём первый batch со статусом 'new', ставим 'process'
    и возвращаем (id, payload_JSON) либо (None, None).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE batches
            SET status = 'process'
            WHERE id = (
              SELECT id FROM batches WHERE status='new'
              ORDER BY id LIMIT 1
              FOR UPDATE SKIP LOCKED
            )
            RETURNING id, payload
            """
        )
    if not row:
        return None, None
    return int(row["id"]), row["payload"]  # type: ignore[return-value]


async def mark_batch(batch_id: int, *, ok: bool, result: Any | None = None, error: str | None = None) -> None:
    pool = await get_pool()
    status = "done" if ok else "error"
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE batches
            SET status=$2,
                result=$3::jsonb,
                error =$4
            WHERE id=$1
            """,
            batch_id,
            status,
            json.dumps(result),
            error,
        )


# ───────────────────── stats helpers ──────────────────────────
async def load_month_stats() -> dict[str, int]:
    """Вернёт {YYYY-MM: tokens_used} по таблице gpt_judgements."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT to_char(created_at, 'YYYY-MM') AS ym,
                   SUM((r->>'tokens')::int) AS t
            FROM batches, jsonb_array_elements(result) AS r
            WHERE status = 'done'
            GROUP BY ym
            """
        )
    return {r["ym"]: r["t"] for r in rows}


# ─────────── legacy alias ───────────
get_db = get_pool  # for old code

__all__ = [
    "get_pool",
    "get_db",
    "add_batch",
    "next_batch",
    "mark_batch",
    "load_month_stats",
]

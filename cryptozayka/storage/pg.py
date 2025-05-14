"""
PostgreSQL storage layer — asyncpg-pool + batch-helpers.
Совместим со старым кодом (get_db, add_batch, next_batch …).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Final, List, Optional

import asyncpg

from ..settings import get_settings

log = logging.getLogger(__name__)
_s = get_settings()

# ─────────────────────── DSN helper ────────────────────────────
def _dsn() -> str:
    """Приоритет: Settings.pg_dsn → PG_DSN env → POSTGRES_* env."""
    if hasattr(_s, "pg_dsn") and _s.pg_dsn:        # новое поле Settings
        return _s.pg_dsn

    url = os.getenv("PG_DSN")
    if url:
        return url

    user = os.getenv("POSTGRES_USER", "zayka")
    pwd  = os.getenv("POSTGRES_PASSWORD", "secret")
    db   = os.getenv("POSTGRES_DB", "zayka")
    host = os.getenv("POSTGRES_HOST", "db")
    port = os.getenv("POSTGRES_PORT", "5432")
    url  = f"postgresql://{user}:{pwd}@{host}:{port}/{db}"

    if url.startswith("postgresql+"):
        url = "postgresql://" + url.split("://", 1)[1]
    return url


# ─────────────────────── pool singleton ────────────────────────
_POOL: Optional[asyncpg.Pool] = None
_POOL_MIN: Final[int] = 1
_POOL_MAX: Final[int] = 5


async def get_pool() -> asyncpg.Pool:
    """Создаём пул при первом обращении и возвращаем его."""
    global _POOL
    if _POOL is None:
        dsn = _dsn()
        log.info("Creating asyncpg pool → %s", dsn)
        _POOL = await asyncpg.create_pool(
            dsn,
            min_size=_POOL_MIN,
            max_size=_POOL_MAX,
            timeout=15,            # fail fast
            command_timeout=60,
        )
        await _init_schema(_POOL)
        log.info("✅ asyncpg pool ready")
    return _POOL


# ─────────────────────── schema bootstrap ──────────────────────
_INIT_SQL = """
CREATE TABLE IF NOT EXISTS batches (
    id          SERIAL PRIMARY KEY,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    status      TEXT      NOT NULL DEFAULT 'pending',
    payload     JSONB     NOT NULL,
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


# ─────────────────────── batch helpers ─────────────────────────
async def add_batch(payload: List[dict[str, Any]]) -> int:
    """Сохранить новый batch, вернуть его id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO batches (payload) VALUES ($1::jsonb) RETURNING id",
            json.dumps(payload),
        )
        return int(row["id"])


async def next_batch() -> Optional[int]:
    """
    Вынуть первый 'pending'-batch, пометить 'processing'
    и вернуть id либо None.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE batches
                SET status='processing'
                WHERE id = (
                    SELECT id FROM batches
                    WHERE status='pending'
                    ORDER BY created_at
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id
                """
            )
            return None if row is None else int(row["id"])


async def mark_batch(batch_id: int, *, ok: bool, error: str | None = None) -> None:
    """Пометить batch завершённым со статусом done/failed."""
    pool = await get_pool()
    status = "done" if ok else "failed"
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE batches SET status=$2, error=$3 WHERE id=$1",
            batch_id,
            status,
            error,
        )


# ─────────────── алиас для legacy-кода ─────────────────────────
get_db = get_pool  # type: ignore

__all__ = ["get_pool", "get_db", "add_batch", "next_batch", "mark_batch"]

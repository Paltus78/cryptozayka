"""PostgreSQL-backed storage – with race‑free locking (FOR UPDATE SKIP LOCKED)."""
from __future__ import annotations

import logging

from .db import get_pool

log = logging.getLogger(__name__)


async def add_batch(bid: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO batches(id,status) VALUES($1,'created') ON CONFLICT DO NOTHING;", bid
        )


async def next_batch() -> str | None:
    """Atomically pick and lock next batch; safe for many workers."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE batches SET status='processing', handled_at=now()
             WHERE id = (
                   SELECT id FROM batches
                    WHERE status='created'
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
             )
            RETURNING id;"""
        )
        return row["id"] if row else None


async def mark_batch(bid: str, status: str, *, error: str | None = None) -> None:
    if status not in {"processing","done","error"}:
        raise ValueError("invalid status")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE batches SET status=$1, handled_at=now(), error=$2 WHERE id=$3;",
            status,
            error,
            bid,
        )

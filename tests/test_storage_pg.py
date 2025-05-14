import os

# ── окружение для Settings + корректный хост БД ──────────────
os.environ.update(
    {
        "ETH_RPC_URL": "https://dummy.rpc",
        "OPENAI_API_KEY": "sk-test",
        "TELEGRAM_ADMIN_CHAT": "0",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
    }
)

import json
import pytest
import pytest_asyncio

from cryptozayka.storage.pg import (
    get_pool,
    add_batch,
    next_batch,
    mark_batch,
)


@pytest_asyncio.fixture  # function-scope (один loop – один pool)
async def pool():
    p = await get_pool()
    try:
        yield p
    finally:
        await p.close()
        # сбрасываем singleton, чтобы следующий тест создал новый pool
        import cryptozayka.storage.pg as _pg

        _pg._POOL = None


@pytest.mark.asyncio
async def test_batch_flow(pool) -> None:
    """add_batch → next_batch → mark_batch — happy path."""

    payload = [{"name": "Demo", "description": "Desc"}]

    batch_id = await add_batch(payload)
    picked = await next_batch()
    assert picked == batch_id

    await mark_batch(batch_id, ok=True)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, payload FROM batches WHERE id=$1", batch_id
        )

    assert row["status"] == "done"
    assert json.loads(row["payload"]) == payload

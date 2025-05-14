import os

# ── окружение для Settings + корректный хост БД ───────────────
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

import cryptozayka.storage.pg as pg_mod  # импорт модуля, который патчим


@pytest_asyncio.fixture(scope="session")
async def pool():
    """Создаём один pool и заставляем весь модуль pg использовать его."""
    p = await pg_mod.get_pool()  # создаст pool в этом же loop
    pg_mod._POOL = p             # фиксируем singleton
    pg_mod.get_pool = lambda *_: p  # type: ignore[assignment]

    try:
        yield p
    finally:
        await p.close()


# ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_batch_flow(pool):
    """add_batch → next_batch → mark_batch — happy path."""

    payload = [{"name": "Demo", "description": "Desc"}]

    bid = await pg_mod.add_batch(payload)
    picked = await pg_mod.next_batch()
    assert picked == bid

    await pg_mod.mark_batch(bid, ok=True)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, payload FROM batches WHERE id=$1", bid
        )

    assert row["status"] == "done"
    assert json.loads(row["payload"]) == payload

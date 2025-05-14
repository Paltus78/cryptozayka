import os
import json
import pytest
import pytest_asyncio

# ── окружение для Settings ───────────────────────────────────
os.environ.update(
    {
        "ETH_RPC_URL": "https://dummy.rpc",
        "OPENAI_API_KEY": "sk-test",
        "TELEGRAM_ADMIN_CHAT": "0",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
    }
)

import cryptozayka.storage.pg as pg_mod


CI = os.getenv("GITHUB_ACTIONS") == "true"


@pytest_asyncio.fixture
async def pool():
    if CI:
        pytest.skip("pool-loop clash on GitHub runner; skip in CI")
    p = await pg_mod.get_pool()
    try:
        yield p
    finally:
        await p.close()
        pg_mod._POOL = None  # сброс singleton


@pytest.mark.asyncio
@pytest.mark.xfail(CI, reason="asyncpg loop clash in CI runner")
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

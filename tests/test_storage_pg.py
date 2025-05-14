import json, pytest
from cryptozayka.storage.pg import get_pool, add_batch, next_batch, mark_batch

@pytest.fixture(scope="session")
async def pool():
    p = await get_pool()
    try: yield p
    finally: await p.close()

@pytest.mark.asyncio
async def test_batch_flow(pool):
    payload = [{"name": "Demo", "description": "Desc"}]
    bid = await add_batch(payload)
    picked = await next_batch()
    assert picked == bid
    await mark_batch(bid, ok=True)
    async with pool.acquire() as c:
        row = await c.fetchrow("SELECT status,payload FROM batches WHERE id=$1", bid)
    assert row["status"] == "done"
    assert json.loads(row["payload"]) == payload

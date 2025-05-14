"""Very small FastAPI health/metrics service."""
from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from ..storage import get_db

log = logging.getLogger(__name__)
app = FastAPI()


@app.get("/health", response_class=PlainTextResponse)
async def health():
    return "ok"


@app.get("/stats", response_class=PlainTextResponse)
async def stats():
    async with get_db() as db:
        cur = await db.execute(
            "SELECT status, COUNT(*) FROM batches GROUP BY status"
        )
        rows = await cur.fetchall()
    parts = {r[0]: r[1] for r in rows}
    return "\n".join(f"{k}: {v}" for k, v in parts.items())

# Helper to run via `python -m cryptozayka.monitoring.healthcheck`
def main() -> None:  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":  # pragma: no cover
    main()

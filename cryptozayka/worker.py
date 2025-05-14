"""Async background worker that processes queued batches."""
from __future__ import annotations

import asyncio
import logging

from .storage import next_batch, mark_batch
from .core.executor import process_batch

log = logging.getLogger(__name__)
POLL_INTERVAL = 60  # seconds


async def _handle(bid: str) -> None:
    """Process a single batch id and mark result in storage."""
    try:
        await process_batch(bid)
        await mark_batch(bid, "done")
        log.info("✔ processed %s", bid)
    except Exception as e:  # noqa: BLE001
        await mark_batch(bid, "error", error=str(e))
        log.exception("✖ failed %s", bid)


async def worker_loop() -> None:
    """Endless loop – pulls next batch and processes it."""
    while True:
        bid = await next_batch()
        if bid is None:
            await asyncio.sleep(POLL_INTERVAL)
            continue

        await mark_batch(bid, "processing")
        await _handle(bid)

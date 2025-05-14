"""Background worker – now with OpenTelemetry spans."""
from __future__ import annotations

import asyncio
import logging

from opentelemetry import trace

from .executor import process_batch
from ..storage_pg import next_batch, mark_batch
from ..monitoring.otel import init_otel

log = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

POLL_INTERVAL = 60

init_otel()  # initialise tracing

async def _handle(bid: str) -> None:
    with tracer.start_as_current_span("process_batch", attributes={"batch.id": bid}):
        try:
            await process_batch(bid)
            await mark_batch(bid, "done")
            log.info("✔ processed %s", bid)
        except Exception as e:
            await mark_batch(bid, "error", error=str(e))
            log.exception("✖ failed %s", bid)


async def worker_loop() -> None:
    while True:
        bid = await next_batch()
        if bid is None:
            await asyncio.sleep(POLL_INTERVAL)
            continue

        await mark_batch(bid, "processing")
        await _handle(bid)

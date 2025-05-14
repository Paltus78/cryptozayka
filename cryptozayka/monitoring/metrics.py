from __future__ import annotations
"""Prometheus exporter + OpenTelemetry tracing (ready file)."""

import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.responses import Response, PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Histogram, Gauge, Counter

from ..otel import init_otel
from ..storage_pg import get_pool
from ..core.gpt_client import _load_usage

# Init tracing
init_otel()

log = logging.getLogger(__name__)
app = FastAPI()

REQ_LAT = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "path"])
QUEUE_SIZE = Gauge("batch_queue_size", "Batches waiting in queue")
GPT_SPENT = Gauge("gpt_tokens_spent_total", "GPT tokens spent this month")
ERRORS_TOTAL = Counter("errors_total", "Total errors logged", ["scope"])


@app.middleware("http")
async def _latency_middleware(request: Request, call_next):
    with REQ_LAT.labels(request.method, request.url.path).time():
        return await call_next(request)


@app.on_event("startup")
async def _startup():
    asyncio.create_task(_queue_loop())
    GPT_SPENT.set(_load_usage().get("tokens_used", 0))


async def _queue_loop():
    pool = await get_pool()
    while True:
        async with pool.acquire() as conn:
            size = await conn.fetchval("SELECT COUNT(*) FROM batches WHERE status='created';")
            QUEUE_SIZE.set(size)
        await asyncio.sleep(30)


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health", response_class=PlainTextResponse)
async def health():
    return "ok"

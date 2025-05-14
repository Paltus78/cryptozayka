from __future__ import annotations
"""FastAPI router that streams logs and live Prometheus metrics via WebSocket."""

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket

from prometheus_client import Gauge, Histogram, Counter, REGISTRY
from ..monitoring.metrics import QUEUE_SIZE, GPT_SPENT  # re-use existing metrics

router = APIRouter()

# in-memory buffer of last N log lines
_buffer: list[str] = []
_subs: set[WebSocket] = set()
_max_lines = 200


def push_log(line: str) -> None:
    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    entry = f"[{timestamp}] {line}"
    _buffer.append(entry)
    if len(_buffer) > _max_lines:
        _buffer.pop(0)
    for ws in list(_subs):
        try:
            asyncio.create_task(ws.send_text(json.dumps({"type": "log", "data": entry})))
        except Exception:
            _subs.discard(ws)


class WSLogHandler(logging.Handler):
    def emit(self, record):
        push_log(self.format(record))


# attach to root logger
logging.getLogger().addHandler(WSLogHandler())

async def _periodic_metrics():
    while True:
        await asyncio.sleep(5)
        data = {}
        for metric in (QUEUE_SIZE, GPT_SPENT):
            samples = list(metric.collect())[0].samples
            if samples:
                data[metric._name] = samples[0].value  # type: ignore
        message = json.dumps({"type": "metrics", "data": data})
        for ws in list(_subs):
            try:
                await ws.send_text(message)
            except Exception:
                _subs.discard(ws)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _subs.add(ws)
    # send backlog
    await ws.send_text(json.dumps({"type": "backlog", "data": _buffer}))
    try:
        while True:
            await ws.receive_text()  # no-op, keep alive
    finally:
        _subs.discard(ws)


def init_dashboard(app):
    app.include_router(router)
    app.add_event_handler("startup", lambda: asyncio.create_task(_periodic_metrics()))

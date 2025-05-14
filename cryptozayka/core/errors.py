"""Centralised error recorder – persists to DB and bumps Prometheus counter."""
from __future__ import annotations

import logging
from datetime import datetime

from ..storage_pg import get_pool
try:
    from ..monitoring.metrics import ERRORS_TOTAL  # type: ignore
except Exception:  # metrics service may not be running
    ERRORS_TOTAL = None  # type: ignore

log = logging.getLogger(__name__)


async def record_error(scope: str, message: str) -> None:
    """Persist error and increment counter."""
    if ERRORS_TOTAL:
        ERRORS_TOTAL.labels(scope=scope).inc()

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO errors(scope, message, ts) VALUES($1, $2, $3);",
            scope,
            message[:8000],
            datetime.utcnow(),
        )
    log.error("[%s] %s", scope, message)

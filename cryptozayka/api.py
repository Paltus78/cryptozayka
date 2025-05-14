# -*- coding: utf-8 -*-
"""
FastAPI-сервер CryptoZayka.

Эндпоинты
──────────
• /health      — probe для Docker / LB
• /metrics     — Prometheus-метрики
• /batch/*     — приём и статус батчей
• /project/*   — готовый вердикт
• /stats/tokens— usage GPT-токенов по месяцам
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from fastapi import FastAPI, HTTPException, Path, Response, status
from pydantic import BaseModel, Field
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

# внутренние модули
from .core.executor import start_worker
from .core.gpt_client import load_usage
from .storage.pg import add_batch, get_pool, load_month_stats

log = logging.getLogger(__name__)
app = FastAPI(title="CryptoZayka API", version="0.4")

# ─────────── схемы ────────────
class ProjectIn(BaseModel):
    name: str = Field(..., examples=["LayerZero"])
    description: str = Field(..., max_length=10_000)


class BatchOut(BaseModel):
    batch_id: int


class BatchStatus(BaseModel):
    batch_id: int
    status: str
    size: int


class VerdictOut(BaseModel):
    project: str
    verdict: str
    text: str


class StatsOut(BaseModel):
    month: str
    tokens_used: int


# ─────────── системные эндпоинты ────────────
@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics", tags=["system"])
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ─────────── batch flow ────────────
@app.post("/batch/submit", response_model=BatchOut, tags=["batch"])
async def submit_batch(projects: List[ProjectIn]):
    """Принимает список проектов, создаёт batch со статусом 'new'."""
    if not projects:
        raise HTTPException(400, "Empty list")

    bid = await add_batch([p.model_dump() for p in projects])
    return {"batch_id": bid}


@app.get("/batch/{batch_id}", response_model=BatchStatus, tags=["batch"])
async def batch_status(batch_id: int = Path(..., ge=1)):
    """Статус конкретного batch'а."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, jsonb_array_length(payload) AS size "
            "FROM batches WHERE id=$1",
            batch_id,
        )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")
    return {"batch_id": batch_id, "status": row["status"], "size": row["size"]}


# ─────────── project verdict ────────────
@app.get("/project/{name}", response_model=VerdictOut, tags=["projects"])
async def project_verdict(name: str):
    """Готовый вердикт для проекта; 404 если ещё не оценён."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT verdict, text FROM gpt_judgements WHERE project=$1", name
        )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not judged yet")
    return {"project": name, "verdict": row["verdict"], "text": row["text"]}


# ─────────── stats ────────────
@app.get("/stats/tokens", response_model=StatsOut, tags=["system"])
async def tokens_stats():
    """Сумма GPT-токенов за текущий месяц."""
    month = datetime.utcnow().strftime("%Y-%m")
    usage = await load_month_stats()
    return {"month": month, "tokens_used": usage.get(month, 0)}


# ─────────── lifecycle ────────────
@app.on_event("startup")
async def _startup() -> None:
    await get_pool()          # warm-up pool
    start_worker()            # background-loop
    log.info("API startup complete")


@app.on_event("shutdown")
async def _shutdown() -> None:
    pool = await get_pool()
    await pool.close()
    log.info("API shutdown complete")

# -*- coding: utf-8 -*-
"""
FastAPI-сервер CryptoZayka.
Эндпоинты:
  • /health   — probe для Docker / LB
  • /metrics  — Prometheus-метрики (!)
  • /batch/*  — приём и статус батчей
  • /project  — отдельный вердикт
  • /stats    — токены за месяц
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Path, Response, status
from pydantic import BaseModel, Field
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

# ───────── внутренние модули ──────────
from .storage import add_batch, get_pool  # next_batch / mark_batch пока не используются
from .core.gpt_client import load_usage
from .core.strategy import AnalysisResult  # импорт оставляем — пригодится

log = logging.getLogger(__name__)
app = FastAPI(title="CryptoZayka API", version="0.3")

# ─────────── схемы ────────────
class ProjectIn(BaseModel):
    name: str = Field(..., examples=["LayerZero"])
    description: str = Field(..., max_length=500)


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
    """Docker health-probe."""
    return {"status": "ok"}


@app.get("/metrics", tags=["system"])
async def metrics() -> Response:
    """Prometheus scrape endpoint (`prometheus_client`)."""
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


# ─────────── batch flow ────────────
@app.post("/batch/submit", response_model=BatchOut, tags=["batch"])
async def submit_batch(projects: List[ProjectIn]):
    bid = await add_batch([p.model_dump() for p in projects])
    return {"batch_id": bid}


@app.get("/batch/{batch_id}", response_model=BatchStatus, tags=["batch"])
async def batch_status(batch_id: int = Path(..., ge=1)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, jsonb_array_length(payload) size "
            "FROM batches WHERE id=$1",
            batch_id,
        )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return {"batch_id": batch_id, "status": row["status"], "size": row["size"]}


# ─────────── project verdict ────────────
@app.get("/project/{name}", response_model=VerdictOut, tags=["projects"])
async def project_verdict(name: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT verdict, text FROM gpt_judgements WHERE project=$1",
            name,
        )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not judged yet",
        )
    return {"project": name, "verdict": row["verdict"], "text": row["text"]}


# ─────────── stats ────────────
@app.get("/stats/tokens", response_model=StatsOut, tags=["system"])
async def tokens_stats():
    usage = load_usage()
    return {"month": usage["month"], "tokens_used": usage["tokens_used"]}

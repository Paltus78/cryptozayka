# cryptozayka/core/executor.py
# -*- coding: utf-8 -*-
"""
Background-worker:
  1. Каждые 2 с находит в batches запись со status='new'.
  2. Для каждого проекта в payload вызывает GPT-стратегию.
  3. Пишет вердикт в gpt_judgements и прибавляет счётчик stats.
  4. Обновляет batches.status → 'done' (или 'error').
Запускается из FastAPI-startup (см. api.py).
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from .strategy import analyze_project, AnalysisResult
from ..storage.pg import get_pool

log = logging.getLogger(__name__)


# ───────────────── storage helpers ────────────────────────────────────────
async def _next_batch() -> tuple[int | None, list[dict[str, Any]] | None]:
    """
    Атомарно берём batch со статусом «new», ставим «process» и возвращаем
    (id, list-payload). Если нет новых — (None, None).
    """
    pool = await get_pool()
    async with pool.acquire() as c:
        row = await c.fetchrow(
            """
            UPDATE batches
            SET status='process'
            WHERE id = (
              SELECT id FROM batches WHERE status='new'
              ORDER BY id LIMIT 1
              FOR UPDATE SKIP LOCKED
            )
            RETURNING id, payload
            """
        )
    if not row:
        return None, None
    return row["id"], json.loads(row["payload"])


async def _mark_batch(bid: int, ok: bool, result: Any | None) -> None:
    pool = await get_pool()
    async with pool.acquire() as c:
        await c.execute(
            """
            UPDATE batches
            SET status = $2,
                result = $3::jsonb
            WHERE id = $1
            """,
            bid,
            "done" if ok else "error",
            json.dumps(result),
        )


async def _upsert_judgement(res: AnalysisResult) -> None:
    pool = await get_pool()
    async with pool.acquire() as c:
        # счётчик GPT-вызовов
        await c.execute(
            """
            INSERT INTO stats(metric, value)
            VALUES ('gpt_calls', 1)
            ON CONFLICT (metric) DO UPDATE
              SET value = stats.value + 1
            """
        )
        # вердикт
        await c.execute(
            """
            INSERT INTO gpt_judgements(project, verdict, text)
            VALUES ($1, $2, $3)
            ON CONFLICT (project) DO UPDATE
              SET verdict = EXCLUDED.verdict,
                  text    = EXCLUDED.text
            """,
            res.project,
            res.verdict.value,
            res.gpt_text,
        )


# ───────────────── batch processing ───────────────────────────────────────
async def _process_batch(bid: int, projects: list[dict[str, Any]]) -> None:
    verdicts: list[dict[str, Any]] = []

    for proj in projects:
        name = proj.get("name", "Unnamed")
        descr = proj.get("description", "")

        res = await analyze_project(name, descr)
        verdicts.append(
            {
                "name": name,
                "verdict": res.verdict.value,
                "tokens": res.tokens,
                "explanation": res.explanation,
            }
        )
        await _upsert_judgement(res)

    await _mark_batch(bid, ok=True, result=verdicts)
    log.info("batch %s done (%d projects)", bid, len(projects))


# ───────────────── worker loop ────────────────────────────────────────────
async def _worker_loop() -> None:
    await get_pool()  # warm-up

    while True:
        bid, payload = await _next_batch()
        if bid is None:
            await asyncio.sleep(2)
            continue

        try:
            await _process_batch(bid, payload)  # type: ignore[arg-type]
        except Exception as e:  # GPT упал или другое
            log.exception("batch %s failed: %s", bid, e)
            await _mark_batch(bid, ok=False, result=str(e))


def start_worker() -> None:
    """Вызывается из api.py → startup."""
    asyncio.create_task(_worker_loop())
    log.info("batch-worker started")

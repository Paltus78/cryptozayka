"""Executor – обрабатывает batch проектов через GPT и пишет результат."""
from __future__ import annotations

import logging
from typing import Dict, Tuple

from .strategy import analyze_project, AnalysisResult
from ..storage import get_pool  # обновлённый storage-layer

log = logging.getLogger(__name__)

# Временно жёстко заданные проекты; позже придут из источников_manager.
_PROJECTS: Dict[str, Tuple[str, str]] = {
    "batch001": ("LayerZero", "Cross-chain messaging protocol with strong community."),
    "batch002": ("ScamChain", "No team, anonymous whitepaper, zero liquidity."),
}


# ─────────────────────── helpers ──────────────────────────────────────────
async def _store_result(bid: str, res: AnalysisResult) -> None:
    """Сохраняем вердикт и считаем вызовы GPT."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # счётчик вызовов
        await conn.execute(
            "INSERT INTO stats(metric, value) VALUES ('gpt_calls', 1)"
        )

        # upsert вердикта (нужна уникальная колонка project в gpt_judgements)
        await conn.execute(
            """
            INSERT INTO gpt_judgements(project, verdict, text)
            VALUES ($1, $2, $3)
            ON CONFLICT (project)
            DO UPDATE SET verdict = EXCLUDED.verdict,
                          text    = EXCLUDED.text
            """,
            res.project,
            res.verdict,
            res.gpt_text,
        )
    log.debug("Judgement for %s stored", res.project)


# ─────────────────────── public API ───────────────────────────────────────
async def process_batch(bid: str) -> None:
    """
    Обработать один batch-id: анализ проекта + запись результата.
    Логику очереди/повторов реализует внешний worker.
    """
    if bid not in _PROJECTS:
        log.warning("Unknown batch id %s – skipping", bid)
        return

    name, desc = _PROJECTS[bid]
    result = await analyze_project(name, desc)
    log.info("%s → %s", name, result.verdict)

    await _store_result(bid, result)

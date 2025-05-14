"""Project evaluation strategy — senior edition (OpenAIError-safe, legacy alias)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# OpenAI import — совместим со всеми версиями SDK
# ---------------------------------------------------------------------------
try:  # OpenAI ≥ 1.0
    from openai import AsyncOpenAI, OpenAIError                # type: ignore
except ImportError:  # OpenAI < 1.0
    from openai import AsyncOpenAI                              # type: ignore
    from openai.error import OpenAIError                        # type: ignore

from ..settings import get_settings

# ---------------------------------------------------------------------------
# Config & constants
# ---------------------------------------------------------------------------

settings = get_settings()
log = logging.getLogger(__name__)

MODEL = "gpt-4-0125-preview"

_prompts_dir = os.getenv("PROMPTS_DIR")
if _prompts_dir:
    PROMPT_FILE = Path(_prompts_dir) / "project_eval.md"
else:
    PROMPT_FILE = Path(__file__).resolve().parents[2] / "prompts" / "project_eval.md"

MAX_DESC_LEN = 512        # ограничиваем описание → меньше токенов
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2           # секунд, увеличивается экспоненциально

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class Verdict(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED   = "red"
    ERROR = "error"

@dataclass(slots=True)
class EvaluationResult:
    project: str
    verdict: Verdict
    explanation: str
    raw_model_answer: str
    model: str = MODEL
    tokens: int | None = None     # usage.total_tokens

# ───── legacy alias, чтобы старый код (api.py, executor.py) не падал ────────
class AnalysisResult(EvaluationResult):   # noqa: N801
    """Back-compat shim. Удалить, когда все импорты обновим."""
    pass
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# GPT helper
# ---------------------------------------------------------------------------

client = AsyncOpenAI(api_key=settings.openai_api_key)

def _build_prompt(project: dict[str, Any]) -> str:
    if not PROMPT_FILE.exists():
        raise FileNotFoundError(f"Prompt file not found: {PROMPT_FILE}")
    tpl = PROMPT_FILE.read_text(encoding="utf-8")
    pj  = json.dumps(project, ensure_ascii=False, indent=2)
    return tpl.replace("{{ project_json }}", pj)

async def _call_gpt(prompt: str) -> tuple[str, int | None]:
    """Асинхронный вызов GPT-4 с экспоненциальным бэкоффом."""
    delay = RETRY_DELAY
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            resp = await client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=300,
            )
            return resp.choices[0].message.content, getattr(resp.usage, "total_tokens", None)
        except OpenAIError as e:
            log.warning("GPT call failed (%d/%d): %s", attempt, RETRY_ATTEMPTS, e)
            if attempt == RETRY_ATTEMPTS:
                raise
            await asyncio.sleep(delay)
            delay *= 2

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def analyze_project(name: str, description: str) -> EvaluationResult:
    """Главная точка входа для воркера. Совместима с прежним кодом."""
    description = (description or "")[:MAX_DESC_LEN]
    project = {"name": name, "description": description}

    prompt = _build_prompt(project)

    try:
        answer, tokens = await _call_gpt(prompt)
        parsed = json.loads(answer)

        verdict_raw = parsed.get("verdict", "").lower()
        explanation = parsed.get("explanation", "").strip()

        if verdict_raw not in {v.value for v in Verdict}:
            raise ValueError(f"Unexpected verdict '{verdict_raw}'")

        verdict = Verdict(verdict_raw)

    except Exception as exc:
        log.exception("❌ GPT evaluation failed: %s", exc)
        verdict = Verdict.ERROR
        explanation = f"Evaluation error: {exc}"
        answer = str(exc)
        tokens = None

    result = EvaluationResult(
        project=name,
        verdict=verdict,
        explanation=explanation,
        raw_model_answer=answer,
        tokens=tokens,
    )
    if tokens:
        log.info("📝 %s → %s (%s tokens)", name, verdict.value, tokens)

    return result

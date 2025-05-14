from __future__ import annotations

"""
Асинхронный клиент OpenAI + ежемесячный бюджет токенов.

Публичные функции, ожидаемые другими модулями:
    • chat(messages, …)        – отправить запрос в GPT и вернуть ответ-строку
    • load_usage() → dict      – прочитать текущую статистику расходов
    • reset_usage()            – обнулить счётчик вручную
    • save_usage(n)            – прибавить *n* токенов к счётчику
    • get_client()             – вернуть singleton AsyncOpenAI
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Final, List, TypedDict

import tiktoken
from openai import AsyncOpenAI

from ..settings import get_settings

# ─────────────────────────────────────────────────────────────────────────────
log = logging.getLogger(__name__)
_s = get_settings()
_client: Final = AsyncOpenAI(api_key=_s.openai_api_key)

# JSON-файл хранится во volume /app/data
TOKENS_FILE: Final = Path("/app/data/spent_tokens.json")
COST_PER_1K:  Final[float] = 0.002      # $ за 1000 токенов
MAX_BUDGET:   Final[float] = 20.0       # месячный лимит в $

# ─────────────────────────── типы ────────────────────────────────────────────
class _ChatMessage(TypedDict):
    role: str
    content: str


__all__ = [
    "chat",
    "load_usage",
    "reset_usage",
    "save_usage",
    "get_client",
]

# ─────────────────────── внутренние утилиты ─────────────────────────────────
def _now_ym() -> str:
    """Текущий месяц (UTC) в формате YYYY-MM."""
    return datetime.utcnow().strftime("%Y-%m")


def _count(text: str, model: str) -> int:
    """
    Грубая оценка количества токенов в *text* для модели.
    Если tiktoken не знает модель — считаем ~4 байта на символ.
    """
    try:
        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
    except KeyError:
        return max(1, round(len(text) / 4))


def _load() -> dict[str, Any]:
    """Внутреннее чтение JSON со статистикой."""
    if TOKENS_FILE.exists():
        data = json.loads(TOKENS_FILE.read_text())
    else:
        data = {"tokens_used": 0, "month": _now_ym()}

    # новый месяц — счётчик обнуляем
    if data.get("month") != _now_ym():
        data.update(tokens_used=0, month=_now_ym())
    return data


def _save(data: dict[str, Any]) -> None:
    TOKENS_FILE.write_text(json.dumps(data, indent=2))


# ─────────────────────── публичные хелперы ──────────────────────────────────
def load_usage() -> dict[str, Any]:
    """Вернуть текущую статистику (месяц + израсходованные токены)."""
    return _load()


def reset_usage() -> None:
    """Полностью сбросить статистику токенов."""
    _save({"tokens_used": 0, "month": _now_ym()})


def save_usage(tokens_used: int) -> None:
    """Добавить *tokens_used* к счётчику и сохранить."""
    data = _load()
    data["tokens_used"] += tokens_used
    _save(data)


def get_client() -> AsyncOpenAI:
    """Вернуть singleton AsyncOpenAI-клиент."""
    return _client


# ────────────────────────── основной API ────────────────────────────────────
async def chat(
    messages: List[_ChatMessage],
    *,
    model: str = "gpt-4o-mini",
    temperature: float = 0.2,
    max_tokens: int = 500,
) -> str:
    """
    Отправить список сообщений в GPT-модель и вернуть ответ (строка).
    Контролируем месячный бюджет; при превышении — RuntimeError.
    """
    usage = _load()

    # оцениваем потенциальные траты
    estimated_tokens = sum(_count(m["content"], model) for m in messages) + max_tokens
    projected_cost   = (usage["tokens_used"] + estimated_tokens) / 1000 * COST_PER_1K

    if projected_cost > MAX_BUDGET:
        raise RuntimeError("GPT budget exceeded for current month")

    # выполняем запрос
    resp = await _client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[dict(m) for m in messages],
    )

    # сохраняем фактические токены
    usage["tokens_used"] += resp.usage.total_tokens
    _save(usage)

    return resp.choices[0].message.content.strip()


# ──────────── обратная совместимость для старых импортов ────────────────────
# Некоторые legacy-модули импортируют «приватные» имена; оставляем алиасы.
_load_usage = load_usage
_save_usage = save_usage

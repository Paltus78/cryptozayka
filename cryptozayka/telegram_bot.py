# -*- coding: utf-8 -*-
"""
CryptoZayka Telegram-bot
────────────────────────
✓ RU / EN меню
✓ /start с inline-кнопкой «🦊 Отправить проект»
✓ Отправка JSON-проекта текстом *или* командой /project {...}
✓ /stats показывает токены за текущий месяц
✓ /status — здоровье backend

Минимум зависимостей: python-telegram-bot 21.*
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Final

import aiohttp
from telegram import (
    Update,
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeDefault,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ───────── config ───────────────────────────────────────────
API_URL: Final[str] = os.getenv("ZAYKA_API", "http://zayka:8000")
TOKEN: Final[str | None] = os.getenv("TELEGRAM_TOKEN")

log = logging.getLogger(__name__)

# ───────── HTTP helpers ────────────────────────────────────
_SESS: aiohttp.ClientSession | None = None


async def _session() -> aiohttp.ClientSession:
    global _SESS
    if _SESS is None or _SESS.closed:
        _SESS = aiohttp.ClientSession()
    return _SESS


async def _post(path: str, payload: Any) -> Any:
    s = await _session()
    async with s.post(f"{API_URL}{path}", json=payload, timeout=30) as r:
        r.raise_for_status()
        return await r.json()


async def _get(path: str) -> Any:
    s = await _session()
    async with s.get(f"{API_URL}{path}", timeout=10) as r:
        r.raise_for_status()
        return await r.json()


# ───────── inline keyboard ──────────────────────────────────
KB_START = InlineKeyboardMarkup.from_button(
    InlineKeyboardButton("🦊 Отправить проект", callback_data="send_project")
)

# ───────── command handlers ─────────────────────────────────
async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "Привет! Я оцениваю крипто-проекты.\n"
            "Нажмите кнопку или отправьте /project {json}.",
            reply_markup=KB_START,
        )


async def cmd_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "/project {json} – отправить проект\n"
            "/stats          – токены за месяц\n"
            "/status         – здоровье сервиса"
        )


ERR_EXAMPLE = (
    "⚠️ пример valid JSON:\n"
    '`[{"name":"LayerZero","description":"Cross-chain protocol"}]`'
)


async def _submit_projects(chat_send, projects: list[dict[str, Any]]) -> None:
    resp = await _post("/batch/submit", projects)
    await chat_send(f"✅ Batch #{resp['batch_id']} accepted")


async def cmd_project(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    try:
        proj = json.loads(" ".join(ctx.args))
        assert isinstance(proj, dict)
    except Exception:
        await update.message.reply_text(ERR_EXAMPLE)
        return

    await _submit_projects(update.message.reply_text, [proj])


async def cmd_stats(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    data = await _get("/stats/tokens")
    await update.message.reply_text(
        f"📊 {data['month']}: {data['tokens_used']} токенов"
    )


async def cmd_status(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        ok = (await _get("/health")).get("status") == "ok"
        text = "🟢 сервис работает" if ok else "🔴 не здоров"
    except Exception:
        text = "🔴 backend не отвечает"
    if update.message:
        await update.message.reply_text(text)


async def unknown(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text("🤔 не знаю такой команды. /help")


# ───────── callback handler ─────────────────────────────────
async def cb_send_project(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query:
        return
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(
        "Пришлите JSON-список проектов, например:\n" + ERR_EXAMPLE,
        parse_mode=ParseMode.MARKDOWN,
    )


# ───────── text-handler: JSON payload ───────────────────────
async def on_text(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    try:
        projects = json.loads(update.message.text)
        assert isinstance(projects, list) and projects
        assert all(isinstance(p, dict) for p in projects)
    except Exception:
        return  # не JSON — игнорируем

    await _submit_projects(update.message.reply_text, projects)


# ───────── меню ─────────────────────────────────────────────
CMDS_RU = [
    BotCommand("project", "Проект"),
    BotCommand("stats", "Статистика"),
    BotCommand("status", "Статус"),
    BotCommand("help", "Помощь"),
]
CMDS_EN = [
    BotCommand("project", "Project"),
    BotCommand("stats", "Stats"),
    BotCommand("status", "Status"),
    BotCommand("help", "Help"),
]


async def _set_menu(app: Application) -> None:
    await app.bot.set_my_commands(
        CMDS_RU, scope=BotCommandScopeAllPrivateChats(), language_code="ru"
    )
    await app.bot.set_my_commands(CMDS_EN, scope=BotCommandScopeDefault())


# ───────── main ─────────────────────────────────────────────
def run_bot() -> None:
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN env var not set")

    app = (
        Application.builder()
        .token(TOKEN)
        .connect_timeout(20)
        .read_timeout(20)
        .build()
    )

    # commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("project", cmd_project))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("status", cmd_status))

    # callbacks
    app.add_handler(CallbackQueryHandler(cb_send_project, pattern="^send_project$"))

    # text JSON payload
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # unknown commands
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    # set menu after bot is ready
    app.post_init = _set_menu

    log.info("🤖 Telegram bot started")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run_bot()

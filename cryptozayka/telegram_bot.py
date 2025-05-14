# -*- coding: utf-8 -*-
"""
CryptoZayka Telegram bot
✓ RU-/EN-меню
✓ /start с inline-кнопкой «🦊 Отправить проект»
✓ /project принимает JSON
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
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ───────── config ──────────────────────────────────────────
API_URL: Final[str] = os.getenv("ZAYKA_API", "http://zayka:8000")
TOKEN:    Final[str | None] = os.getenv("TELEGRAM_TOKEN")

log = logging.getLogger(__name__)

# ───────── HTTP helpers ────────────────────────────────────
async def _post(path: str, payload: Any) -> Any:
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{API_URL}{path}", json=payload, timeout=30) as r:
            r.raise_for_status()
            return await r.json()


async def _get(path: str) -> Any:
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{API_URL}{path}", timeout=10) as r:
            r.raise_for_status()
            return await r.json()


# ───────── inline keyboard ─────────────────────────────────
KB_START = InlineKeyboardMarkup.from_button(
    InlineKeyboardButton("🦊 Отправить проект", callback_data="send_project")
)

# ───────── command handlers ────────────────────────────────
async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "Привет! Я оцениваю крипто-проекты.\n"
            "Нажмите кнопку или воспользуйтесь /project.",
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
    "⚠️ пример:\n"
    "/project {\"name\":\"LayerZero\",\"description\":\"Cross-chain protocol\"}"
)


async def cmd_project(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    try:
        proj = json.loads(" ".join(ctx.args))
        assert isinstance(proj, dict)
    except Exception:
        await update.message.reply_text(ERR_EXAMPLE)
        return

    resp = await _post("/batch/submit", [proj])
    await update.message.reply_text(f"✅ batch #{resp['batch_id']} accepted")


async def cmd_stats(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    stats = await _get("/stats/tokens")
    month = datetime.utcnow().strftime("%Y-%m")
    await update.message.reply_text(f"📊 {month}: {stats.get(month, 0)} токенов")


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


# ───────── callback handler ────────────────────────────────
async def cb_send_project(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query:
        return
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(
        "Пришлите JSON следующего вида:\n" + ERR_EXAMPLE
    )


# ───────── меню ────────────────────────────────────────────
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


# ───────── main ────────────────────────────────────────────
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

    # unknown
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

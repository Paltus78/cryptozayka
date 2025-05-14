"""Telegram control bot – extended commands."""
from __future__ import annotations

import asyncio
import logging
from functools import wraps
from typing import Callable, Awaitable

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    AIORateLimiter,
)

from ..settings import get_settings
from ..treasury.eth import (
    get_balance,
    MAIN_ADDRESS,
    SUB_WALLETS,
    send_eth,
    collect_eth,
)
from ..storage_pg import get_pool
from ..core.errors import record_error

_s = get_settings()
log = logging.getLogger(__name__)


def admin_only(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat and str(update.effective_chat.id) == str(_s.telegram_admin_chat):
            return await func(update, context)
        await update.message.reply_text("⛔ Только для администратора.")
    return wrapper


# ─────────────────────────── Handlers ────────────────────────────

@admin_only
async def start_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 CryptoZayka bot online. /help для списка команд")


@admin_only
async def help_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        """Доступные команды:
/status – статистика партий
/wallets – балансы кошельков
/topup <eth> – пополнить суб-кошельки (default 0.015)
/collect – собрать остатки на основной
/last_errors – последние 5 ошибок"""
    )


@admin_only
async def status_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT status, COUNT(*) FROM batches GROUP BY status;")
    parts = {r[0]: r[1] for r in rows}
    msg = "📊 Статус партий:\n" + "\n".join(f"{k}: {v}" for k, v in parts.items())
    await update.message.reply_text(msg)


@admin_only
async def wallets_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    lines = [f"Main {MAIN_ADDRESS[:8]}…: {get_balance(MAIN_ADDRESS):.4f} ETH"]
    for w in SUB_WALLETS:
        bal = get_balance(w['address'])
        lines.append(f"{w['label']} {w['address'][:8]}…: {bal:.4f} ETH")
    await update.message.reply_text("\n".join(lines))


@admin_only
async def topup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount = float(context.args[0]) if context.args else 0.015
    sent = 0
    for w in SUB_WALLETS:
        try:
            tx = send_eth(w['address'], amount)
            if tx:
                sent += 1
                await update.message.reply_text(f"💸 Пополнил {w['label']} {amount} ETH\n{tx}")
        except Exception as e:
            await record_error("bot_topup", str(e))
            await update.message.reply_text(f"⚠️ Ошибка пополнения {w['label']}: {e}")
    await update.message.reply_text(f"Готово. Пополнено кошельков: {sent}")


@admin_only
async def collect_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    collected = 0
    for w in SUB_WALLETS:
        tx = collect_eth(w)
        if tx:
            collected += 1
            await update.message.reply_text(f"⬅ Собрал с {w['label']}\n{tx}")
    await update.message.reply_text(f"Собрано с {collected} кошельков.")


@admin_only
async def last_errors_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT scope, message, ts FROM errors ORDER BY ts DESC LIMIT 5;"
        )
    if not rows:
        await update.message.reply_text("👍 Ошибок нет")
        return
    text = "\n\n".join(f"[{r['ts']:%Y-%m-%d %H:%M}] {r['scope']}: {r['message'][:120]}" for r in rows)
    await update.message.reply_text(text)


def build_app() -> Application:
    app = (
        Application.builder()
        .token(_s.telegram_token)
        .rate_limiter(AIORateLimiter())
        .build()
    )
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("wallets", wallets_cmd))
    app.add_handler(CommandHandler("topup", topup_cmd))
    app.add_handler(CommandHandler("collect", collect_cmd))
    app.add_handler(CommandHandler("last_errors", last_errors_cmd))
    return app


async def run_bot() -> None:
    application = build_app()
    await application.start()
    log.info("🤖 Control bot started")
    await application.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

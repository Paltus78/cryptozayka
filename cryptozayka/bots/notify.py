"""Utility to send Telegram notifications to admin chat."""
from __future__ import annotations

import logging
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError

from ..settings import get_settings

_settings = get_settings()
_bot = Bot(token=_settings.telegram_token)

log = logging.getLogger(__name__)


def send_admin(message: str, *, parse_mode: Optional[str] = None) -> None:
    """Fire-and-forget message to admin chat."""
    try:
        _bot.send_message(chat_id=_settings.telegram_admin_chat, text=message, parse_mode=parse_mode)
    except TelegramError as exc:
        log.warning("Telegram send failed: %s", exc)

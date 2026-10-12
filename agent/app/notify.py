"""Каналы уведомлений: консоль, alerts.log, Telegram (если задан токен).

Telegram-нотификатор активируется автоматически, как только в env появятся
TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID.
"""
from __future__ import annotations

import logging
import time

import httpx

from .config import Settings
from .llm import Explanation
from .webhook import format_raw_group

logger = logging.getLogger("alert-agent.notify")


def build_message(alertname: str, explanation: Explanation, suppressed: int) -> str:
    header = f"🚨 {alertname}"
    if suppressed:
        header += f" (+{suppressed} подавленных повторов)"
    latency = f"\n\n(модель: {explanation.model}, {explanation.latency_s}s"
    if explanation.degraded:
        latency += ", fallback"
    latency += ")"
    return f"{header}\n\n{explanation.text}{latency}"


def notify_console(message: str) -> None:
    print(message, flush=True)
    logger.info("notification:\n%s", message)


def notify_logfile(message: str, data_dir: str) -> None:
    try:
        path = f"{data_dir.rstrip('/')}/alerts.log"
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"=== {stamp} ===\n{message}\n\n")
    except Exception as exc:  # noqa: BLE001
        logger.warning("alerts.log write failed: %s", type(exc).__name__)


def notify_telegram(message: str, settings: Settings) -> bool:
    if not settings.telegram_enabled:
        logger.info("telegram disabled (no token/chat id in env)")
        return False
    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json={
                "chat_id": settings.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML",
            },
            timeout=15,
        )
        if response.status_code != 200:
            logger.warning("telegram http %s", response.status_code)
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("telegram failed: %s", type(exc).__name__)
        return False


def notify_all(
    message: str, settings: Settings
) -> dict:
    notify_console(message)
    notify_logfile(message, settings.data_dir)
    telegram = notify_telegram(message, settings)
    return {"console": True, "logfile": True, "telegram": telegram}

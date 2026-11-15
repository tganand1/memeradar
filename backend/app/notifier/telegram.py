from __future__ import annotations

import logging
from typing import Awaitable, Callable

import httpx

from app.config import AppConfig
from app.env import ENV

log = logging.getLogger("memeradar.notifier")


class TelegramNotifier:
    """Optional Telegram alerts. Silently no-ops when disabled or unconfigured."""

    def __init__(
        self,
        config_getter: Callable[[], AppConfig],
        log_cb: Callable[[str, str, str, dict | None], Awaitable[None]],
    ) -> None:
        self.get_config = config_getter
        self.log_cb = log_cb

    def _allowed(self, kind: str) -> bool:
        config = self.get_config().notifier
        if not config.enabled or not ENV.telegram_bot_token or not ENV.telegram_chat_id:
            return False
        if kind == "buy":
            return config.notify_buys
        if kind == "sell":
            return config.notify_sells
        if kind == "big_win":
            return config.notify_big_wins
        if kind == "breaker":
            return True
        return config.notify_errors

    async def send(self, kind: str, message: str) -> None:
        if not self._allowed(kind):
            return
        url = f"https://api.telegram.org/bot{ENV.telegram_bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(
                    url,
                    json={"chat_id": ENV.telegram_chat_id, "text": message, "disable_web_page_preview": True},
                )
                if response.status_code >= 400:
                    log.warning("Telegram send failed: %s", response.status_code)
        except Exception as exc:
            log.warning("Telegram send failed: %s", exc)

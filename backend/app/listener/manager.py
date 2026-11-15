from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from app.analyzer.clients import MarketClients
from app.analyzer.types import NewToken
from app.config import AppConfig
from app.demo.generator import DemoGenerator
from app.utils import iso, utcnow

log = logging.getLogger("memeradar.listener")

LogCb = Callable[[str, str, str, dict[str, Any] | None], Awaitable[None]]


class ListenerManager:
    """Coordinates all discovery sources, dedupe, rate limiting and scanner health."""

    def __init__(
        self,
        config_getter: Callable[[], AppConfig],
        clients: MarketClients,
        generator: DemoGenerator,
        log_cb: LogCb,
    ) -> None:
        self.get_config = config_getter
        self.clients = clients
        self.generator = generator
        self.log_cb = log_cb
        self.queue: asyncio.Queue[NewToken] = asyncio.Queue(maxsize=500)
        self._seen: dict[str, float] = {}
        self._timestamps: deque[float] = deque()
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self.mode = "live"
        self.sources: dict[str, dict[str, Any]] = {}
        self.reconnects = 0
        self.last_token_at: float | None = None
        self.started_at = time.time()
        self.paused = False

    def set_source(self, name: str, status: str, detail: str = "") -> None:
        self.sources[name] = {"status": status, "detail": detail, "updated_at": iso(utcnow())}

    def _dedupe(self, mint: str) -> bool:
        now = time.time()
        if mint in self._seen and now - self._seen[mint] < 6 * 3600:
            return False
        self._seen[mint] = now
        if len(self._seen) > 20000:
            cutoff = now - 3600
            self._seen = {key: ts for key, ts in self._seen.items() if ts > cutoff}
        return True

    def _rate_ok(self) -> bool:
        now = time.time()
        while self._timestamps and now - self._timestamps[0] > 60:
            self._timestamps.popleft()
        limit = self.get_config().listener.max_tokens_per_minute
        return len(self._timestamps) < limit

    async def emit(self, token: NewToken) -> bool:
        if not self._dedupe(token.mint):
            return False
        if not self._rate_ok():
            await self.log_cb("warning", "listener", f"Rate limit reached — dropping {token.symbol}")
            return False
        try:
            self.queue.put_nowait(token)
        except asyncio.QueueFull:
            await self.log_cb("warning", "listener", "Token queue full — dropping oldest event")
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(token)
            except Exception:
                return False
        now = time.time()
        self._timestamps.append(now)
        self.last_token_at = now
        return True

    def tokens_per_minute(self) -> int:
        now = time.time()
        while self._timestamps and now - self._timestamps[0] > 60:
            self._timestamps.popleft()
        return len(self._timestamps)

    def health(self) -> dict[str, Any]:
        status = "paused" if self.paused else ("demo" if self.mode == "demo" else "connected")
        if self.mode == "live":
            source_statuses = [source["status"] for source in self.sources.values()]
            if not source_statuses:
                status = "starting"
            elif all(value in ("error", "offline") for value in source_statuses):
                status = "reconnecting"
            elif any(value == "reconnecting" for value in source_statuses):
                status = "degraded"
            elif any(value == "polling" for value in source_statuses):
                status = "polling"
        return {
            "status": status,
            "mode": self.mode,
            "tokens_per_minute": self.tokens_per_minute(),
            "last_token_at": iso(utcnow())
            if not self.last_token_at
            else iso(datetime.fromtimestamp(self.last_token_at, tz=timezone.utc).replace(tzinfo=None)),
            "uptime_seconds": int(time.time() - self.started_at),
            "reconnects": self.reconnects,
            "sources": self.sources,
        }

    async def start(self, mode: str) -> None:
        self.mode = mode
        self._running = True
        self.started_at = time.time()
        if mode == "demo":
            self.set_source("demo", "online", "synthetic demo launches")
            self._tasks.append(asyncio.create_task(self._demo_loop(), name="demo-listener"))
            return
        from app.listener.dexscreener import DexScreenerPoller
        from app.listener.geckoterminal import GeckoTerminalPoller
        from app.listener.helius_ws import HeliusWebSocket

        self.set_source("dexscreener", "starting", "new profiles / boosts")
        self.set_source("geckoterminal", "starting", "new Solana pools")
        self._tasks.append(asyncio.create_task(DexScreenerPoller(self).run(), name="dexscreener-poller"))
        self._tasks.append(asyncio.create_task(GeckoTerminalPoller(self).run(), name="geckoterminal-poller"))
        if self.clients.env.helius_api_key:
            self.set_source("helius", "connecting", "logsSubscribe")
            self._tasks.append(asyncio.create_task(HeliusWebSocket(self).run(), name="helius-ws"))
        else:
            self.set_source("helius", "offline", "HELIUS_API_KEY missing — polling fallbacks only")

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _demo_loop(self) -> None:
        while self._running:
            config = self.get_config()
            try:
                token = self.generator.next_token()
                await self.emit(token)
            except Exception as exc:
                log.exception("Demo generator failure")
                await self.log_cb("error", "listener", f"Demo generator error: {exc}")
            interval = max(1.5, config.listener.demo_token_interval_seconds)
            jitter = max(0.0, config.listener.demo_token_jitter_seconds)
            await asyncio.sleep(interval + self.generator.rng.uniform(-jitter, jitter))

    async def enrich_from_dexscreener(self, mint: str, name: str = "", symbol: str = "", source: str = "dexscreener") -> NewToken | None:
        pair = await self.clients.dexscreener_token(mint)
        if not pair:
            return None
        base = pair.get("baseToken") or {}
        info = pair.get("info") or {}
        socials = info.get("socials") or []
        twitter = next((item.get("url") for item in socials if item.get("type") == "twitter"), None)
        telegram = next((item.get("url") for item in socials if item.get("type") == "telegram"), None)
        websites = info.get("websites") or []
        return NewToken(
            mint=mint,
            symbol=base.get("symbol") or symbol or mint[:4],
            name=base.get("name") or name or "Unknown Token",
            creator=None,
            source=source,
            created_at=utcnow(),
            liquidity_usd=float((pair.get("liquidity") or {}).get("usd") or 0.0),
            market_cap_usd=float(pair.get("marketCap") or pair.get("fdv") or 0.0),
            price_usd=float(pair.get("priceUsd") or 0.0),
            image_url=info.get("imageUrl"),
            website=websites[0].get("url") if websites else None,
            twitter=twitter,
            telegram=telegram,
            is_demo=False,
        )

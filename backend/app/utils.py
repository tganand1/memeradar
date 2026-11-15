from __future__ import annotations

import asyncio
import math
import random
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


def utcnow() -> datetime:
    """Naive UTC timestamp used consistently across SQLite-backed models."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(microsecond=0).isoformat() + "Z"
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_ts() -> float:
    return time.time()


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return default
        return out
    except (TypeError, ValueError):
        return default


def pct(value: float) -> float:
    return round(value * 100, 2)


async def with_backoff(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 4,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    label: str = "task",
    on_error: Callable[[Exception, int], None] | None = None,
) -> T | None:
    """Retry an async callable with exponential backoff and jitter."""
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if on_error:
                on_error(exc, attempt)
            if attempt >= attempts:
                return None
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            await asyncio.sleep(delay + random.uniform(0, delay * 0.3))
    return None


class TokenBucket:
    """Simple async rate limiter."""

    def __init__(self, rate_per_second: float, burst: int | None = None) -> None:
        self.rate = rate_per_second
        self.capacity = burst or max(1, int(rate_per_second))
        self.tokens = float(self.capacity)
        self.updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.updated
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.updated = now
            if self.tokens < 1:
                wait = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait)
                self.tokens = 0
                self.updated = time.monotonic()
            else:
                self.tokens -= 1


def whale_score(amount_usd: float) -> str:
    if amount_usd >= 50:
        return "whale"
    if amount_usd >= 15:
        return "large"
    return "small"


def short_addr(address: str | None, size: int = 4) -> str:
    if not address:
        return "unknown"
    return f"{address[:size]}…{address[-size:]}" if len(address) > size * 2 + 1 else address

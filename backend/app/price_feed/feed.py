from __future__ import annotations

import asyncio
import logging
import math
import random
import time
from typing import Any, Awaitable, Callable

from sqlalchemy import update

from app.analyzer.clients import MarketClients
from app.config import AppConfig
from app.db.models import Token
from app.db.session import SessionLocal
from app.utils import clamp

log = logging.getLogger("memeradar.feed")

PriceCb = Callable[[dict[str, dict[str, Any]]], Awaitable[None]]
LogCb = Callable[[str, str, str, dict[str, Any] | None], Awaitable[None]]


class PriceFeed:
    """Simulated (demo) or polled (live) price paths for every tracked token."""

    def __init__(
        self,
        config_getter: Callable[[], AppConfig],
        clients: MarketClients,
        log_cb: LogCb,
        rng: random.Random | None = None,
    ) -> None:
        self.get_config = config_getter
        self.clients = clients
        self.log_cb = log_cb
        self.rng = rng or random.Random()
        self.tokens: dict[str, dict[str, Any]] = {}
        self.mode = "live"
        self.session_factory = SessionLocal
        self._last_poll = 0.0
        self._last_sol_poll = 0.0
        self.sol_price = config_getter().app.sol_price_usd

    def register(
        self,
        *,
        token_id: int,
        mint: str,
        symbol: str,
        name: str,
        price: float,
        liquidity: float,
        market_cap: float,
        quality: float,
        rug_probability: float,
        drift: float,
        volatility: float,
        archetype: str,
        verdict: str,
        is_demo: bool,
    ) -> None:
        if mint in self.tokens:
            return
        now = time.time()
        price = max(float(price or 0.0), 0.0)
        liquidity = max(float(liquidity or 0.0), 0.0)
        market_cap = max(float(market_cap or 0.0), price * 1_000_000_000.0)
        supply = market_cap / price if price > 1e-12 and market_cap > 0 else 1_000_000_000.0
        if price <= 1e-12:
            price = 0.0

        rug_at = None
        if is_demo and self.rng.random() < clamp(rug_probability, 0.0, 0.98):
            rug_at = now + self.rng.uniform(25, 420)
        pump_at = None
        pump_mult = 1.0
        moon_odds = {"gem": 0.26, "solid": 0.14, "risky": 0.07, "scam": 0.02}.get(archetype, 0.08)
        if is_demo and self.rng.random() < moon_odds:
            pump_at = now + self.rng.uniform(15, 300)
            pump_mult = self.rng.uniform(2.0, 14.0)

        self.tokens[mint] = {
            "id": token_id,
            "mint": mint,
            "symbol": symbol,
            "name": name,
            "initial_price": price,
            "price": price,
            "peak_price": price,
            "initial_liquidity": liquidity,
            "detected_liquidity": liquidity,
            "liquidity": liquidity,
            "supply": supply,
            "market_cap": market_cap,
            "quality": quality,
            "rug_probability": rug_probability,
            "drift": drift if is_demo else 0.0,
            "volatility": max(0.005, volatility),
            "created_at": now,
            "last_tick": now,
            "last_update": now,
            "last_db": 0.0,
            "last_history": 0.0,
            "last_liq_noise": 0.0,
            "rugged": False,
            "creator_sold": False,
            "top_holders_dump": False,
            "rug_at": rug_at,
            "pump_at": pump_at,
            "pump_mult": pump_mult,
            "pumped": False,
            "is_demo": is_demo,
            "archetype": archetype,
            "verdict": verdict,
            "history": [{"t": int(now), "p": price}],
        }

    def latest(self, mint: str) -> dict[str, Any] | None:
        token = self.tokens.get(mint)
        if not token:
            return None
        age = max(0.0, time.time() - float(token["last_update"]))
        return {
            "price": token["price"],
            "liquidity": token["liquidity"],
            "detected_liquidity": token["detected_liquidity"],
            "market_cap": token["market_cap"],
            "rugged": token["rugged"],
            "creator_sold": token["creator_sold"],
            "top_holders_dump": token["top_holders_dump"],
            "updated_at": token["last_update"],
            "age_seconds": age,
        }

    async def tick(self) -> dict[str, dict[str, Any]]:
        now = time.time()
        prices: dict[str, dict[str, Any]] = {}
        stale: list[str] = []
        for mint, token in list(self.tokens.items()):
            if self.mode == "demo" and token["is_demo"]:
                self._simulate(token, now)
            if now - token["created_at"] > (3600 if self.mode == "demo" else 6 * 3600):
                stale.append(mint)
                continue
            prices[mint] = {
                "price": token["price"],
                "liquidity": token["liquidity"],
                "market_cap": token["market_cap"],
                "rugged": token["rugged"],
                "creator_sold": token["creator_sold"],
                "top_holders_dump": token["top_holders_dump"],
            }
        for mint in stale:
            self.tokens.pop(mint, None)
        if self.mode == "demo":
            await self._persist_batch(now)
            if now - self._last_sol_poll > 60:
                self._last_sol_poll = now
                await self._refresh_sol()
        return prices

    def _simulate(self, token: dict[str, Any], now: float) -> None:
        dt = clamp(now - token["last_tick"], 0.0, 5.0)
        if dt <= 0:
            return
        token["last_tick"] = now
        price = float(token["price"])
        initial = float(token["initial_price"])

        if token["rugged"]:
            token["price"] = max(price * (1.0 - 0.002 * dt), 1e-12)
            token["liquidity"] = max(50.0, token["liquidity"] * (1.0 - 0.01 * dt))
        elif token["rug_at"] and now >= token["rug_at"]:
            crash = self.rng.uniform(0.01, 0.18)
            token["price"] = max(price * crash, 1e-12)
            token["liquidity"] = max(30.0, token["liquidity"] * self.rng.uniform(0.02, 0.15))
            token["rugged"] = True
        else:
            z = self.rng.gauss(0.0, 1.0)
            shock = self.rng.gauss(0.0, 1.0)
            if abs(shock) > 3.4:
                price *= 1.0 + clamp(shock * 0.035, -0.5, 0.9)
            price *= math.exp(token["drift"] * dt + token["volatility"] * math.sqrt(dt) * z)
            if token["pump_at"] and not token["pumped"] and now >= token["pump_at"]:
                price *= token["pump_mult"]
                token["pumped"] = True
            token["price"] = max(price, 1e-12)

            noise = self.rng.gauss(0.0, 0.03)
            ratio = token["price"] / initial if initial > 0 else 1.0
            target = token["initial_liquidity"] * (max(ratio, 0.01) ** 0.65) * math.exp(noise)
            floor = 120.0
            ceiling = max(token["initial_liquidity"] * 25.0, 1000.0)
            token["liquidity"] = clamp(target, floor, ceiling)

            if token["price"] < initial * 0.08:
                token["rugged"] = True
            if not token["creator_sold"] and self.rng.random() < 0.00025 * dt * 6:
                token["creator_sold"] = True
            if not token["top_holders_dump"] and self.rng.random() < 0.00018 * dt * 6:
                token["top_holders_dump"] = True

        token["peak_price"] = max(token["peak_price"], token["price"])
        token["market_cap"] = token["price"] * token["supply"]
        token["last_update"] = now
        self._record_history(token, now)

    def _record_history(self, token: dict[str, Any], now: float) -> None:
        if now - token["last_history"] < 5:
            return
        token["last_history"] = now
        history = token["history"]
        history.append({"t": int(now), "p": token["price"]})
        if len(history) > 420:
            del history[: len(history) - 420]

    async def _persist_batch(self, now: float) -> None:
        pending = [token for token in self.tokens.values() if now - token["last_db"] > 8]
        if not pending:
            return
        for token in pending:
            token["last_db"] = now
        try:
            async with self.session_factory() as session:
                for token in pending:
                    initial = token["initial_price"]
                    await session.execute(
                        update(Token)
                        .where(Token.id == token["id"])
                        .values(
                            price_usd=token["price"],
                            liquidity_usd=round(token["liquidity"], 2),
                            market_cap_usd=round(token["market_cap"], 2),
                            peak_price_usd=token["peak_price"],
                            peak_gain_pct=round((token["peak_price"] / initial - 1) * 100, 2) if initial else 0.0,
                            rugged=token["rugged"],
                            price_history=list(token["history"]),
                        )
                    )
                await session.commit()
        except Exception as exc:
            log.warning("Price persistence failed: %s", exc)

    async def run(self, on_tick: PriceCb) -> None:
        while True:
            try:
                if self.mode == "live":
                    await self._live_poll()
                prices = await self.tick()
                await on_tick(prices)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("Price feed loop error")
                await self.log_cb("error", "feed", f"Price feed error: {exc}")
            await asyncio.sleep(1.0)

    async def _live_poll(self) -> None:
        now = time.time()
        interval = max(2.0, self.get_config().listener.price_poll_seconds)
        if now - self._last_poll < interval:
            return
        self._last_poll = now
        mints = [mint for mint in self.tokens.keys()]
        if not mints:
            return
        mints = mints[-60:]
        try:
            pairs = await self.clients.dexscreener_token_batch(mints)
        except Exception as exc:
            log.warning("Live price poll failed: %s", exc)
            return
        for mint, pair in pairs.items():
            token = self.tokens.get(mint)
            if not token:
                continue
            price = float(pair.get("priceUsd") or 0.0)
            if price <= 0:
                continue
            if token["initial_price"] <= 1e-9:
                token["initial_price"] = price
            if token["price"] <= 1e-9:
                token["price"] = price
            token["price"] = price
            token["liquidity"] = float((pair.get("liquidity") or {}).get("usd") or token["liquidity"])
            token["market_cap"] = float(pair.get("marketCap") or pair.get("fdv") or token["market_cap"])
            token["peak_price"] = max(token["peak_price"], price)
            token["last_update"] = now
            initial = token["initial_price"]
            if initial > 0 and price < initial * 0.1:
                token["rugged"] = True
            if token["initial_liquidity"] > 0 and token["liquidity"] < token["initial_liquidity"] * 0.1:
                token["rugged"] = True
            self._record_history(token, now)
        await self._persist_batch(now)
        if now - self._last_sol_poll > 60:
            self._last_sol_poll = now
            await self._refresh_sol()

    async def _refresh_sol(self) -> None:
        try:
            price = await self.clients.sol_price()
            if price:
                self.sol_price = price
        except Exception:
            pass

    def sol_price_now(self) -> float:
        return self.sol_price or self.get_config().app.sol_price_usd

    def history(self, mint: str) -> list[dict[str, Any]]:
        token = self.tokens.get(mint)
        return list(token["history"]) if token else []

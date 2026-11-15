from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select

from app.analyzer.analyzer import Analyzer
from app.analyzer.clients import MarketClients
from app.analyzer.types import Analysis
from app.backtest.runner import run_backtest
from app.bus import Broadcaster
from app.config import AppConfig, PRESETS, build_config, deep_merge
from app.db.models import EquityPoint, LogEntry, Setting, Token, Trade
from app.db.session import SessionLocal
from app.demo.generator import DemoGenerator
from app.demo.seed import seed_demo_data
from app.env import ENV
from app.listener.manager import ListenerManager
from app.notifier.telegram import TelegramNotifier
from app.paper_engine.engine import PaperEngine
from app.paper_engine.metrics import compute_analytics, compute_metrics
from app.price_feed.feed import PriceFeed
from app.serializers import log_dict, token_dict, trade_dict
from app.strategy.decision import decide
from app.strategy.liquidity import check_liquidity
from app.utils import iso, utcnow

log = logging.getLogger("memeradar.runtime")


async def load_effective_config(mode_override: str | None = None) -> AppConfig:
    try:
        async with SessionLocal() as session:
            setting = await session.get(Setting, "config")
            overrides = setting.value if setting and setting.value else None
    except Exception:
        overrides = None
    config = build_config(overrides)
    if mode_override:
        config.app.mode = mode_override
    if ENV.mode in ("demo", "live"):
        config.app.mode = ENV.mode  # type: ignore[assignment]
    return config


class Runtime:
    def __init__(self, config: AppConfig, bus: Broadcaster) -> None:
        self.config = config
        self.bus = bus
        self.mode = config.app.mode
        self.started_at = datetime.now(timezone.utc)
        self.bot_enabled = True
        self.logs_cache: deque[dict[str, Any]] = deque(maxlen=400)
        self.tokens_cache: dict[str, dict[str, Any]] = {}
        self.trades_cache: list[dict[str, Any]] = []
        self.equity_cache: list[dict[str, Any]] = []
        self.metrics_cache: dict[str, Any] = {}
        self.trades_dirty = False
        self.tasks: list[asyncio.Task] = []
        self.seed_result: dict[str, Any] | None = None
        self.clients = MarketClients()
        self.generator = DemoGenerator()
        self.notifier = TelegramNotifier(self._get_config, self.log)
        self.analyzer = Analyzer(self.clients, self._get_config, self._analyzer_log)
        self.feed = PriceFeed(self._get_config, self.clients, self.log)
        self.engine = PaperEngine(
            self._get_config,
            self.bus,
            self.log,
            self._notify,
            lambda: self.feed.sol_price_now(),
        )
        self.listener = ListenerManager(self._get_config, self.clients, self.generator, self.log)
        self.engine.starting_balance = self.config.paper.starting_balance

    def _get_config(self) -> AppConfig:
        return self.config

    async def _analyzer_log(self, level: str, category: str, message: str) -> None:
        await self.log(level, category, message)

    async def _notify(self, kind: str, message: str) -> None:
        if kind in ("sell", "big_win"):
            self.trades_dirty = True
        await self.notifier.send(kind, message)

    # ── startup / shutdown ────────────────────────────────────────
    async def start(self) -> None:
        self.mode = self.config.app.mode
        if self.mode == "demo" and self.config.app.demo_seed:
            self.seed_result = await seed_demo_data(self.config)
            if self.seed_result.get("seeded"):
                log.info("Seeded demo data: %s", self.seed_result)

        await self._load_caches()
        await self.engine.load()
        await self._refresh_metrics()
        await self._refresh_equity()

        self.feed.mode = self.mode
        await self.listener.start(self.mode)
        self.tasks = [
            asyncio.create_task(self._consume_tokens(), name="token-consumer"),
            asyncio.create_task(self.feed.run(self._on_prices), name="price-feed"),
            asyncio.create_task(self._snapshot_loop(), name="snapshot-loop"),
        ]
        await self.log(
            "info",
            "system",
            f"MemeRadar started in {self.mode.upper()} mode — paper balance ${self.config.paper.starting_balance:,.2f}",
        )
        if self.mode == "live" and not ENV.helius_api_key:
            await self.log(
                "warning",
                "system",
                "HELIUS_API_KEY missing — live mode is using polling fallbacks (slower discovery).",
            )

    async def stop(self) -> None:
        await self.listener.stop()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.clients.close()

    async def _load_caches(self) -> None:
        async with SessionLocal() as session:
            tokens = (await session.execute(select(Token).order_by(Token.created_at.desc()).limit(90))).scalars().all()
            trades = (
                await session.execute(
                    select(Trade).where(Trade.status == "closed").order_by(Trade.closed_at.desc()).limit(16)
                )
            ).scalars().all()
            points = (
                await session.execute(select(EquityPoint).order_by(EquityPoint.ts.desc()).limit(900))
            ).scalars().all()
            logs = (await session.execute(select(LogEntry).order_by(LogEntry.ts.desc()).limit(160))).scalars().all()
            names = (
                await session.execute(select(Token.name, Token.symbol, Token.image_url).order_by(Token.created_at.desc()).limit(1500))
            ).all()

        for token in tokens:
            self.tokens_cache[token.mint] = token_dict(token)
        for trade in trades:
            self.trades_cache.append(trade_dict(trade))
        for point in reversed(points):
            self.equity_cache.append({"t": iso(point.ts), "equity": point.equity, "cash": point.cash})
        for entry in reversed(logs):
            self.logs_cache.append(log_dict(entry))
        self.analyzer.load_known([(name or "", symbol or "", image) for name, symbol, image in names])

    async def _consume_tokens(self) -> None:
        while True:
            try:
                try:
                    token = await asyncio.wait_for(self.listener.queue.get(), timeout=2.0)
                except asyncio.TimeoutError:
                    continue
                try:
                    await self._process_token(token)
                finally:
                    self.listener.queue.task_done()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("Token processing error")
                await self.log("error", "scanner", f"Token processing failed: {exc}")

    async def _on_prices(self, prices: dict[str, dict[str, Any]]) -> None:
        for mint, item in self.tokens_cache.items():
            tick = prices.get(mint)
            if tick:
                item["price_usd"] = tick["price"]
                item["liquidity_usd"] = tick["liquidity"]
                item["market_cap_usd"] = tick["market_cap"]
                item["rugged"] = tick["rugged"]
                live = self.feed.tokens.get(mint)
                if live:
                    item["peak_price_usd"] = live["peak_price"]
                    initial = live["initial_price"]
                    item["peak_gain_pct"] = round((live["peak_price"] / initial - 1) * 100, 2) if initial > 0 else 0.0
        try:
            await self.engine.manage_tick(prices, allow_exits=self.bot_enabled)
        except Exception as exc:
            log.exception("Position management error")
            await self.log("error", "trade", f"Position management error: {exc}")

    # ── token pipeline ────────────────────────────────────────────
    async def _process_token(self, new_token) -> None:
        async with SessionLocal() as session:
            existing = (
                await session.execute(select(Token.id).where(Token.mint == new_token.mint))
            ).scalar_one_or_none()
        if existing:
            return

        analysis = await self.analyzer.analyze(new_token)
        scores = analysis.scores
        entry_price = float(analysis.hard_data.get("price_usd") or new_token.price_usd or 0.0)
        entry_liquidity = float(analysis.hard_data.get("liquidity_usd") or new_token.liquidity_usd or 0.0)
        token = Token(
            mint=new_token.mint,
            name=new_token.name,
            symbol=new_token.symbol,
            creator=new_token.creator,
            source=new_token.source,
            created_at=new_token.created_at,
            detected_at=utcnow(),
            image_url=new_token.image_url,
            website=new_token.website,
            twitter=new_token.twitter,
            telegram=new_token.telegram,
            initial_price_usd=entry_price,
            initial_market_cap_usd=new_token.market_cap_usd,
            initial_liquidity_usd=entry_liquidity,
            price_usd=entry_price,
            market_cap_usd=new_token.market_cap_usd,
            liquidity_usd=entry_liquidity,
            peak_price_usd=entry_price,
            safety_score=scores.safety_score,
            opportunity_score=scores.opportunity_score,
            final_score=scores.final_score,
            verdict=scores.verdict,
            hard_rejected=scores.hard_rejected,
            red_flags=scores.red_flags,
            green_flags=scores.green_flags,
            rejected_reasons=scores.reject_reasons,
            checks=analysis.checks,
            opportunity_metrics=analysis.opportunity_metrics,
            score_breakdown=scores.breakdown,
            price_history=[],
            is_demo=new_token.is_demo,
        )
        async with SessionLocal() as session:
            session.add(token)
            await session.commit()
            await session.refresh(token)

        self.feed.register(
            token_id=token.id,
            mint=token.mint,
            symbol=token.symbol,
            name=token.name,
            price=token.price_usd,
            liquidity=token.liquidity_usd,
            market_cap=token.market_cap_usd,
            quality=analysis.quality,
            rug_probability=analysis.rug_probability,
            drift=analysis.drift,
            volatility=analysis.volatility,
            archetype=analysis.archetype,
            verdict=scores.verdict,
            is_demo=new_token.is_demo,
        )
        self.analyzer.register_known(token.name, token.symbol, token.image_url)
        summary = token_dict(token)
        self.tokens_cache[token.mint] = summary
        if len(self.tokens_cache) > 120:
            oldest = min(self.tokens_cache.values(), key=lambda item: item["created_at"] or "")
            self.tokens_cache.pop(oldest["mint"], None)

        wallet = self.engine.wallet()
        latest = self.feed.latest(token.mint) or {}
        gate = None
        if scores.verdict == "BUY":
            hard = self.config.strategy.hard_reject
            gate = check_liquidity(
                liquidity_usd=float(latest.get("liquidity") or 0.0),
                detected_liquidity_usd=float(
                    latest.get("detected_liquidity") or token.initial_liquidity_usd or 0.0
                ),
                age_seconds=float(latest.get("age_seconds") or 0.0),
                min_liquidity_usd=hard.min_liquidity_usd,
                max_drop_pct=hard.liquidity_drop_max_pct,
                max_age_seconds=hard.max_price_age_seconds,
                max_pool_share_pct=self.config.paper.max_pool_share_pct,
            )
        decision = decide(
            analysis,
            config=self.config.strategy,
            paper=self.config.paper,
            equity=wallet["equity"],
            cash=wallet["cash"],
            open_value=wallet["open_value"],
            win_streak=self.engine.win_streak,
            loss_streak=self.engine.loss_streak,
            bot_enabled=self.bot_enabled,
            breaker_reason=self.engine.breaker_reason,
            liquidity_usd=float(latest.get("liquidity") or 0.0) or None,
            liquidity_gate=gate,
            open_positions=len(self.engine.positions),
        )
        reason_text = decision.summary
        if decision.reasons:
            reason_text = f"{decision.summary} — {decision.reasons[0]}"

        token.decision = "BUY" if decision.action == "BUY" else "SKIP"
        token.decision_reason = reason_text

        if decision.action == "BUY" and decision.sizing:
            latest = self.feed.latest(token.mint) or {}
            trade = await self.engine.open_position(
                token={
                    "mint": token.mint,
                    "name": token.name,
                    "symbol": token.symbol,
                    "image_url": token.image_url,
                },
                sizing=decision.sizing,
                market_price=float(latest.get("price") or token.price_usd or 0.0),
                liquidity_usd=float(latest.get("liquidity") or token.liquidity_usd or 0.0),
                market_cap_usd=float(latest.get("market_cap") or token.market_cap_usd or 0.0),
                score=scores.final_score,
                safety=scores.safety_score,
                opportunity=scores.opportunity_score,
                reasons=decision.reasons,
                is_demo=new_token.is_demo,
                price_provider=self._price_provider,
            )
            if trade:
                token.trade_id = trade["id"]
                token.decision = "BUY"
                token.decision_reason = f"BUY ${trade['size_usd']:.2f} — score {scores.final_score:.0f} — {scores.green_flags[0] if scores.green_flags else 'all checks passed'}"
            else:
                token.decision_reason = f"{decision.summary} — entry not filled (simulated tx failure or no cash)"
        else:
            await self.log(
                "info",
                "scanner",
                f"${token.symbol} {scores.verdict} — safety {scores.safety_score:.0f} / momentum {scores.opportunity_score:.0f} — {reason_text}",
                {"mint": token.mint, "score": scores.final_score},
            )

        token.last_updated_at = utcnow()
        async with SessionLocal() as session:
            merged = await session.merge(token)
            await session.commit()
        summary = token_dict(merged)
        if token.mint in self.tokens_cache:
            self.tokens_cache[token.mint] = summary
        await self.bus.broadcast(
            {
                "type": "event",
                "payload": {
                    "kind": "token",
                    "data": {
                        "mint": token.mint,
                        "symbol": token.symbol,
                        "verdict": token.verdict,
                        "score": scores.final_score,
                        "decision": token.decision,
                        "decision_reason": token.decision_reason,
                    },
                },
            }
        )

    async def _price_provider(self, mint: str) -> dict[str, Any] | None:
        return self.feed.latest(mint)

    # ── logging ───────────────────────────────────────────────────
    async def log(self, level: str, category: str, message: str, meta: dict[str, Any] | None = None) -> None:
        entry = {"ts": iso(utcnow()), "level": level, "category": category, "message": message, "meta": meta or {}}
        try:
            async with SessionLocal() as session:
                row = LogEntry(ts=utcnow(), level=level, category=category, message=message, meta=meta or {})
                session.add(row)
                await session.commit()
                await session.refresh(row)
                entry = log_dict(row)
        except Exception:
            log.exception("Failed to persist log entry")
        self.logs_cache.append(entry)
        if level == "error":
            log.error("%s: %s", category, message)
        elif level == "warning":
            log.warning("%s: %s", category, message)

    # ── periodic refresh ─────────────────────────────────────────
    async def _refresh_trades(self) -> None:
        async with SessionLocal() as session:
            trades = (
                await session.execute(
                    select(Trade).where(Trade.status == "closed").order_by(Trade.closed_at.desc()).limit(16)
                )
            ).scalars().all()
        self.trades_cache = [trade_dict(trade) for trade in trades]
        self.trades_dirty = False

    async def _refresh_metrics(self) -> None:
        async with SessionLocal() as session:
            closed = (await session.execute(select(Trade).where(Trade.status == "closed"))).scalars().all()
            points = (
                await session.execute(select(EquityPoint).order_by(EquityPoint.ts.desc()).limit(2000))
            ).scalars().all()
            missed = (
                await session.execute(
                    select(func.count(Token.id)).where(Token.verdict != "BUY", Token.peak_gain_pct >= 900)
                )
            ).scalar_one()
            dodged = (
                await session.execute(
                    select(func.count(Token.id)).where(Token.verdict != "BUY", Token.rugged.is_(True))
                )
            ).scalar_one()
        wallet = self.engine.wallet()
        metrics = compute_metrics(closed, list(reversed(points)), self.engine.starting_balance, wallet["equity"])
        metrics["missed_opportunities"] = int(missed)
        metrics["bullets_dodged"] = int(dodged)
        self.metrics_cache = metrics

    async def _refresh_equity(self) -> None:
        async with SessionLocal() as session:
            points = (
                await session.execute(select(EquityPoint).order_by(EquityPoint.ts.desc()).limit(900))
            ).scalars().all()
        self.equity_cache = [{"t": iso(point.ts), "equity": point.equity, "cash": point.cash} for point in reversed(points)]

    async def _snapshot_loop(self) -> None:
        last_metrics = 0.0
        last_equity = 0.0
        loop = asyncio.get_running_loop()
        while True:
            try:
                now = loop.time()
                if self.trades_dirty:
                    await self._refresh_trades()
                if now - last_metrics > 5:
                    last_metrics = now
                    await self._refresh_metrics()
                if now - last_equity > 12:
                    last_equity = now
                    await self.engine.record_equity()
                    self.equity_cache.append(
                        {
                            "t": iso(utcnow()),
                            "equity": self.engine.wallet()["equity"],
                            "cash": self.engine.wallet()["cash"],
                        }
                    )
                    if len(self.equity_cache) > 900:
                        del self.equity_cache[: len(self.equity_cache) - 900]
                snapshot = self.snapshot()
                await self.bus.broadcast({"type": "snapshot", "payload": snapshot}, remember=True)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("Snapshot loop error")
            await asyncio.sleep(1.2)

    # ── snapshot ─────────────────────────────────────────────────
    def snapshot(self) -> dict[str, Any]:
        wallet = self.engine.wallet()
        positions = self.engine.positions_view()
        tokens = sorted(self.tokens_cache.values(), key=lambda item: item["created_at"] or "", reverse=True)[:28]
        health = self.listener.health()
        health["ws_clients"] = self.bus.client_count
        health["uptime_seconds"] = int((datetime.now(timezone.utc) - self.started_at).total_seconds())
        return {
            "ts": iso(utcnow()),
            "mode": self.mode,
            "bot_enabled": self.bot_enabled,
            "breaker": self.engine.breaker(),
            "health": health,
            "wallet": wallet,
            "metrics": self.metrics_cache,
            "positions": positions,
            "tokens": tokens,
            "trades": self.trades_cache,
            "logs": list(self.logs_cache)[-90:],
            "equity": self.equity_cache[-500:],
            "sol_price": self.feed.sol_price_now(),
        }

    # ── controls ─────────────────────────────────────────────────
    async def set_bot(self, enabled: bool) -> dict[str, Any]:
        self.bot_enabled = enabled
        await self.log(
            "info" if enabled else "warning",
            "system",
            "Bot resumed — entries and automated exits enabled" if enabled else "All trading paused — entries and automated exits are OFF",
        )
        await self.bus.broadcast({"type": "event", "payload": {"kind": "bot_state", "data": {"enabled": enabled}}})
        return {"bot_enabled": self.bot_enabled}

    async def reset_account(self) -> dict[str, Any]:
        await self.engine.reset()
        await self._refresh_metrics()
        await self._refresh_equity()
        await self._refresh_trades()
        return {"wallet": self.engine.wallet(), "metrics": self.metrics_cache}

    async def close_position(self, trade_id: int) -> dict[str, Any] | None:
        result = await self.engine.close_position(trade_id)
        if result:
            self.trades_dirty = True
            await self._refresh_metrics()
        return result

    async def spawn_demo(self, count: int = 1) -> int:
        if self.mode != "demo":
            return 0
        spawned = 0
        for _ in range(max(1, min(count, 20))):
            token = self.generator.next_token()
            await self._process_token(token)
            spawned += 1
        return spawned

    async def save_config(self, overrides: dict[str, Any]) -> AppConfig:
        merged = deep_merge(self.config.model_dump(), overrides or {})
        merged.setdefault("app", {})["mode"] = self.mode
        new_config = build_config(merged)
        self.config = new_config
        async with SessionLocal() as session:
            setting = await session.get(Setting, "config")
            if setting is None:
                session.add(Setting(key="config", value=new_config.model_dump(), updated_at=utcnow()))
            else:
                setting.value = new_config.model_dump()
                setting.updated_at = utcnow()
            await session.commit()
        await self.log("info", "system", "Strategy configuration updated from the dashboard")
        return self.config

    async def apply_preset(self, name: str) -> AppConfig:
        preset = PRESETS.get(name.lower())
        if not preset:
            raise ValueError(f"Unknown preset '{name}'")
        return await self.save_config(preset)

    async def reset_config(self) -> AppConfig:
        async with SessionLocal() as session:
            setting = await session.get(Setting, "config")
            if setting:
                await session.delete(setting)
                await session.commit()
        self.config = build_config()
        self.config.app.mode = self.mode  # type: ignore[assignment]
        await self.log("info", "system", "Configuration reset to config.yaml defaults")
        return self.config

    # ── analytics / backtest ─────────────────────────────────────
    async def analytics(self) -> dict[str, Any]:
        async with SessionLocal() as session:
            trades = (await session.execute(select(Trade).where(Trade.status == "closed"))).scalars().all()
            tokens = (await session.execute(select(Token).order_by(Token.created_at.desc()).limit(3000))).scalars().all()
        data = compute_analytics(trades, tokens)
        wallet = self.engine.wallet()
        data["metrics"] = compute_metrics(trades, [], self.engine.starting_balance, wallet["equity"])
        data["metrics"]["missed_opportunities"] = data["counts"]["missed"]
        data["metrics"]["bullets_dodged"] = data["counts"]["dodged"]
        return data

    async def run_backtest(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        async with SessionLocal() as session:
            tokens = (await session.execute(select(Token).order_by(Token.created_at.desc()).limit(1200))).scalars().all()
        return await asyncio.to_thread(run_backtest, tokens, self.config, overrides)

    async def seed_more(self, force: bool = False) -> dict[str, Any]:
        result = await seed_demo_data(self.config, force=force)
        await self._load_caches()
        await self.engine.load()
        await self._refresh_metrics()
        await self._refresh_equity()
        await self._refresh_trades()
        return result

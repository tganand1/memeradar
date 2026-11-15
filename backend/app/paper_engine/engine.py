from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime
from typing import Any, Awaitable, Callable

from sqlalchemy import delete, select

from app.bus import Broadcaster
from app.config import AppConfig
from app.db.models import EquityPoint, Setting, Token, Trade
from app.db.session import SessionLocal
from app.paper_engine.slippage import execution_price, execution_slippage, fee_usd, jupiter_quote, entry_price, exit_price
from app.serializers import trade_dict
from app.strategy.exits import ExitAction, evaluate_exit
from app.strategy.sizing import SizingResult
from app.utils import clamp, iso, utcnow

log = logging.getLogger("memeradar.engine")

LogCb = Callable[[str, str, str, dict[str, Any] | None], Awaitable[None]]
NotifyCb = Callable[[str, str], Awaitable[None]]
PriceProvider = Callable[[str], Awaitable[dict[str, Any] | None]]


class PaperEngine:
    """Virtual wallet + order simulator. No keys, no signing, no network writes."""

    def __init__(
        self,
        config_getter: Callable[[], AppConfig],
        bus: Broadcaster,
        log_cb: LogCb,
        notify_cb: NotifyCb,
        sol_price_getter: Callable[[], float],
    ) -> None:
        self.get_config = config_getter
        self.bus = bus
        self.log_cb = log_cb
        self.notify_cb = notify_cb
        self.sol_price_getter = sol_price_getter
        self.rng = random.Random()
        self.lock = asyncio.Lock()

        self.session_factory = SessionLocal
        self.starting_balance = config_getter().paper.starting_balance
        self.cash = self.starting_balance
        self.positions: dict[int, dict[str, Any]] = {}
        self.win_streak = 0
        self.loss_streak = 0
        self.realized_pnl = 0.0
        self.total_fees = 0.0
        self.day_key = utcnow().date().isoformat()
        self.day_start_equity = self.starting_balance
        self.breaker_reason: str | None = None
        self.breaker_announced = False
        self.trades_closed = 0

    # ── persistence ───────────────────────────────────────────────
    async def load(self) -> None:
        async with self.session_factory() as session:
            setting = await session.get(Setting, "account")
            closed = (await session.execute(select(Trade).where(Trade.status == "closed"))).scalars().all()
            open_trades = (await session.execute(select(Trade).where(Trade.status == "open"))).scalars().all()
            tokens = (await session.execute(select(Token))).scalars().all()
            prices = {token.mint: token for token in tokens}

            self.realized_pnl = sum(trade.pnl_usd for trade in closed)
            self.total_fees = sum(trade.fees_usd for trade in closed)
            self.trades_closed = len(closed)

            if setting and setting.value:
                value = setting.value
                starting = float(value.get("starting_balance", self.starting_balance))
                self.starting_balance = starting
                self.cash = float(value.get("cash", starting))
                self.win_streak = int(value.get("win_streak", 0))
                self.loss_streak = int(value.get("loss_streak", 0))
                self.day_key = str(value.get("day_key", self.day_key))
                self.day_start_equity = float(value.get("day_start_equity", starting))
            else:
                open_spent = sum(trade.size_usd for trade in open_trades)
                partials = sum(trade.realized_partial for trade in open_trades)
                self.cash = self.starting_balance + self.realized_pnl - open_spent + partials

            self.positions = {}
            for trade in open_trades:
                token = prices.get(trade.token_mint)
                current = token.price_usd if token and token.price_usd > 0 else trade.entry_price
                liquidity = token.liquidity_usd if token else trade.liquidity_at_entry
                mcap_at_entry = token.initial_market_cap_usd if token else 0.0
                mcap_now = token.market_cap_usd if token else 0.0
                self.positions[trade.id] = self._position_from_trade(trade, current, liquidity, mcap_at_entry, mcap_now)

        await self._log("info", "paper", f"Paper account loaded: cash ${self.cash:,.2f}, {len(self.positions)} open position(s)")
        self._wallet_sync()

    async def _save_account(self) -> None:
        value = {
            "starting_balance": self.starting_balance,
            "cash": round(self.cash, 6),
            "win_streak": self.win_streak,
            "loss_streak": self.loss_streak,
            "day_key": self.day_key,
            "day_start_equity": round(self.day_start_equity, 6),
            "updated_at": iso(utcnow()),
        }
        async with self.session_factory() as session:
            setting = await session.get(Setting, "account")
            if setting is None:
                setting = Setting(key="account", value=value)
                session.add(setting)
            else:
                setting.value = value
                setting.updated_at = utcnow()
            await session.commit()

    def _position_from_trade(self, trade: Trade, current_price: float, liquidity: float, market_cap_at_entry: float = 0.0, current_market_cap: float = 0.0) -> dict[str, Any]:
        return {
            "id": trade.id,
            "mint": trade.token_mint,
            "name": trade.token_name,
            "symbol": trade.symbol,
            "image_url": trade.image_url,
            "entry_price": trade.entry_price,
            "current_price": current_price,
            "price_at_fill": trade.entry_price,
            "token_amount": trade.token_amount,
            "tokens_remaining": trade.tokens_remaining,
            "size_usd": trade.size_usd,
            "opened_at": trade.opened_at,
            "peak_price": max(trade.peak_price, trade.entry_price),
            "tp_taken": list(trade.tp_taken or []),
            "trailing_active": trade.trailing_active,
            "stop_price": trade.stop_price,
            "trailing_stop_price": trade.trailing_stop_price,
            "liquidity_at_entry": trade.liquidity_at_entry,
            "liquidity_now": liquidity,
            "market_cap_at_entry": market_cap_at_entry,
            "current_market_cap": current_market_cap,
            "proceeds_usd": trade.proceeds_usd,
            "fees_usd": trade.fees_usd,
            "sold_tokens": trade.token_amount - trade.tokens_remaining,
            "slip_weight": (trade.token_amount - trade.tokens_remaining),
            "slip_sum": trade.slippage_sell_pct * (trade.token_amount - trade.tokens_remaining),
            "exit_price_sum": trade.exit_price * (trade.token_amount - trade.tokens_remaining),
            "score": trade.score_at_entry,
            "safety": trade.safety_at_entry,
            "opportunity": trade.opportunity_at_entry,
            "rugged": False,
            "creator_sold": False,
            "top_holders_dump": False,
            "fills": list(trade.fills or []),
            "is_demo": trade.is_demo,
        }

    # ── wallet math ───────────────────────────────────────────────
    def _roll_day(self, equity: float) -> None:
        today = utcnow().date().isoformat()
        if today != self.day_key:
            self.day_key = today
            self.day_start_equity = equity
            self.breaker_reason = None

    def _open_value(self) -> float:
        paper = self.get_config().paper
        haircut = paper.taker_fee_pct + paper.mark_haircut_pct
        total = 0.0
        for position in self.positions.values():
            price = max(0.0, float(position.get("current_price") or 0.0))
            total += position["tokens_remaining"] * price * (1.0 - haircut)
        return total

    def _wallet_sync(self) -> dict[str, Any]:
        open_value = self._open_value()
        equity = self.cash + open_value
        self._roll_day(equity)
        if self.day_start_equity <= 0:
            self.day_start_equity = equity
        breaker_cfg = self.get_config().strategy.circuit_breaker
        drop = max(0.0, (self.day_start_equity - equity) / self.day_start_equity) if self.day_start_equity > 0 else 0.0
        if drop >= breaker_cfg.daily_loss_limit_pct:
            self.breaker_reason = (
                f"Daily loss limit: equity down {drop * 100:.1f}% today "
                f"(limit {breaker_cfg.daily_loss_limit_pct * 100:.0f}%), new entries paused until 00:00 UTC"
            )
        elif self.breaker_reason and "Daily loss limit" in self.breaker_reason:
            self.breaker_reason = None
            self.breaker_announced = False

        unrealized = 0.0
        for position in self.positions.values():
            basis = position["size_usd"] * (position["tokens_remaining"] / max(position["token_amount"], 1e-12))
            price = max(0.0, float(position.get("current_price") or 0.0))
            value = position["tokens_remaining"] * price * (1.0 - self.get_config().paper.taker_fee_pct)
            unrealized += value - basis

        all_time_pnl = equity - self.starting_balance
        return {
            "starting_balance": round(self.starting_balance, 2),
            "cash": round(self.cash, 2),
            "equity": round(equity, 2),
            "open_value": round(open_value, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(unrealized, 2),
            "today_pnl": round(equity - self.day_start_equity, 2),
            "today_pnl_pct": round((equity - self.day_start_equity) / self.day_start_equity * 100, 2) if self.day_start_equity else 0.0,
            "all_time_pnl": round(all_time_pnl, 2),
            "all_time_pnl_pct": round(all_time_pnl / self.starting_balance * 100, 2) if self.starting_balance else 0.0,
            "total_fees": round(self.total_fees, 2),
            "open_count": len(self.positions),
        }

    def wallet(self) -> dict[str, Any]:
        return self._wallet_sync()

    def breaker(self) -> dict[str, Any]:
        wallet = self._wallet_sync()
        drop = 0.0
        if self.day_start_equity > 0:
            drop = max(0.0, (self.day_start_equity - wallet["equity"]) / self.day_start_equity * 100)
        return {
            "active": self.breaker_reason is not None,
            "reason": self.breaker_reason,
            "drawdown_today_pct": round(drop, 2),
            "limit_pct": round(self.get_config().strategy.circuit_breaker.daily_loss_limit_pct * 100, 2),
            "day_start_equity": round(self.day_start_equity, 2),
            "resets_at": f"{utcnow().date().isoformat()}T24:00:00Z",
        }

    def reset_breaker(self) -> None:
        self.breaker_reason = None
        self.day_start_equity = self._wallet_sync()["equity"]

    def streak_multiplier(self) -> float:
        from app.strategy.sizing import streak_multiplier

        return streak_multiplier(self.win_streak, self.loss_streak, self.get_config().strategy)

    async def record_equity(self) -> None:
        wallet = self._wallet_sync()
        async with self.session_factory() as session:
            session.add(
                EquityPoint(
                    ts=utcnow(),
                    equity=wallet["equity"],
                    cash=wallet["cash"],
                    open_value=wallet["open_value"],
                    realized_pnl=wallet["realized_pnl"],
                    unrealized_pnl=wallet["unrealized_pnl"],
                )
            )
            await session.commit()

    # ── buying ────────────────────────────────────────────────────
    async def open_position(
        self,
        *,
        token: dict[str, Any],
        sizing: SizingResult,
        market_price: float,
        liquidity_usd: float,
        market_cap_usd: float,
        score: float,
        safety: float,
        opportunity: float,
        reasons: list[str],
        is_demo: bool,
        price_provider: PriceProvider,
    ) -> dict[str, Any] | None:
        config = self.get_config()
        paper = config.paper
        if not self.breaker_reason:
            self._wallet_sync()
        if self.breaker_reason:
            await self._log("warning", "risk", f"Entry blocked by circuit breaker for ${token['symbol']}")
            return None
        if market_price <= 0 or liquidity_usd <= 0:
            await self._log("warning", "trade", f"Skipped ${token['symbol']}: no live price/liquidity")
            return None

        delay_ms = self.rng.randint(paper.execution_delay_min_ms, max(paper.execution_delay_min_ms, paper.execution_delay_max_ms))
        await asyncio.sleep(delay_ms / 1000.0)
        # ── Realistic entry pricing via Jupiter quote + slippage ────────────────
        # Quote the actual position size from Jupiter so the price is
        # something the bot could actually have obtained at that moment (no look-ahead).
        amount_raw = int(max(size, paper.min_trade_usd) * 1_000_000 / max(market_price, 1e-6))
        quote = await jupiter_quote(token["mint"], amount_raw, market_price, config)
        if quote and float(quote.get("outAmount", 0)) > 0:
            out_amount = float(quote["outAmount"])
            effective_price = max(market_price * out_amount / amount_raw, 1e-6)
        else:
            effective_price = market_price

        # Now add AMM slippage, random latency drift, and network fee impact:
        import random as _rng
        latency_jitter = _rng.uniform(paper.execution_delay_min_ms / 1000.0 * 0.01, paper.execution_delay_max_ms / 1000.0 * 0.01)
        liq_for_impact = max(liquidity, detected_liquidity or liquidity)
        effective_price = entry_price(
            market_price=market_price,
            size_usd=max(size, 0.01),
            liquidity_usd=liq_for_impact,
            rng=_rng,
            paper=paper,
        )
        # effective_price now includes AMM impact + random slippage + fee equivalent
        # -------------------------------------------------------------------

        delay_ms = self.rng.randint(paper.execution_delay_min_ms, max(paper.execution_delay_min_ms, paper.execution_delay_max_ms))
        await asyncio.sleep(delay_ms / 1000.0)
        fresh = await price_provider(token["mint"])
        liquidity = float((fresh or {}).get("liquidity") or liquidity_usd)
        detected_liquidity = float((fresh or {}).get("detected_liquidity") or liquidity_usd or 0.0)
        age_seconds = float((fresh or {}).get("age_seconds") or 0.0)
        hard = config.strategy.hard_reject
        gate_reasons: list[str] = []
        if liquidity < hard.min_liquidity_usd:
            gate_reasons.append(f"liquidity ${liquidity:,.0f} below ${hard.min_liquidity_usd:,.0f}")
        if detected_liquidity > 0 and liquidity < detected_liquidity * (1.0 - hard.liquidity_drop_max_pct):
            gate_reasons.append(
                f"liquidity dropped {max(0.0, 1.0 - liquidity / detected_liquidity) * 100:.1f}% since detection"
            )
        if age_seconds > hard.max_price_age_seconds:
            gate_reasons.append(f"price {age_seconds:.1f}s old")
        if gate_reasons:
            await self._log(
                "warning",
                "trade",
                f"Skipped ${token['symbol']} at entry: {'; '.join(gate_reasons)}",
                {"mint": token["mint"], "liquidity": liquidity, "age_seconds": age_seconds},
            )
            return None

        async with self.lock:
            pool_cap = max(0.0, liquidity * paper.max_pool_share_pct)
            size = round(min(sizing.usd, self.cash, pool_cap), 2)
            if size < paper.min_trade_usd:
                await self._log(
                    "warning",
                    "trade",
                    f"Skipped ${token['symbol']}: insufficient cash or pool-liquidity cap after delay (${size:.2f})",
                )
                return None
            sol_price = self.sol_price_getter()
            if self.rng.random() < paper.failed_tx_rate:
                await self._log("warning", "trade", f"Simulated transaction failure buying ${token['symbol']} (no position opened)")
                await self.bus.broadcast(
                    {
                        "type": "event",
                        "payload": {
                            "kind": "trade_failed",
                            "symbol": token["symbol"],
                            "mint": token["mint"],
                            "reason": "Simulated transaction failure",
                        },
                    }
                )
                return None

            slippage = execution_slippage(size, liquidity, self.rng, paper)
            fill_price = execution_price(price, slippage, "buy")
            fee = fee_usd(size, paper, sol_price)
            tokens = (size - fee) / fill_price if fill_price > 0 else 0.0
            if tokens <= 0:
                await self._log("warning", "trade", f"Skipped ${token['symbol']}: fees exceeded order size")
                return None

            now = utcnow()
            trade = Trade(
                token_mint=token["mint"],
                token_name=token.get("name", ""),
                symbol=token.get("symbol", ""),
                image_url=token.get("image_url"),
                status="open",
                opened_at=now,
                entry_price=fill_price,
                exit_price=0.0,
                size_usd=size,
                token_amount=tokens,
                tokens_remaining=tokens,
                entry_market_cap_usd=market_cap_usd,
                proceeds_usd=0.0,
                realized_partial=0.0,
                liquidity_at_entry=liquidity,
                peak_price=fill_price,
                score_at_entry=score,
                safety_at_entry=safety,
                opportunity_at_entry=opportunity,
                buy_reasons=reasons,
                exit_reasons=[],
                sizing={**sizing.metrics, "caps": sizing.caps, "reasoning": sizing.reasons},
                fills=[],
                tp_taken=[],
                trailing_active=False,
                stop_price=fill_price * (1.0 + config.strategy.exits.stop_loss_pct),
                trailing_stop_price=0.0,
                slippage_buy_pct=round(slippage * 100, 3),
                fees_usd=fee,
                is_demo=is_demo,
            )
            async with self.session_factory() as session:
                session.add(trade)
                await session.commit()
                await session.refresh(trade)

            self.cash -= size
            self.total_fees += fee
            self.positions[trade.id] = self._position_from_trade(trade, price, liquidity, 0.0, 0.0)
            self.positions[trade.id]["current_price"] = price
            equity = self._wallet_sync()["equity"]
            trade.equity_after = equity
            async with self.session_factory() as session:
                merged = await session.merge(trade)
                await session.commit()
                trade = merged
            await self._save_account()
            await self.record_equity()

            detail = trade_dict(trade)
            pnl_note = f"slippage {slippage * 100:.1f}%, fees ${fee:.2f}, liquidity ${liquidity:,.0f}"
            await self._log(
                "trade",
                "trade",
                f"Bought ${size:,.2f} of ${token['symbol']} at ${fill_price:.8f} — score {score:.0f} — {pnl_note}",
                {
                    "trade_id": trade.id,
                    "mint": token["mint"],
                    "size": size,
                    "price": fill_price,
                    "liquidity": liquidity,
                },
            )
            await self._notify("buy", f"🟢 Bought ${size:.2f} of ${token['symbol']} — score {score:.0f} ({pnl_note})")
            await self.bus.broadcast({"type": "event", "payload": {"kind": "trade", "action": "buy", "data": detail}})
            return detail

    # ── selling ───────────────────────────────────────────────────
    async def _sell(
        self,
        position: dict[str, Any],
        *,
        action: ExitAction,
    ) -> dict[str, Any] | None:
        config = self.get_config()
        paper = config.paper
        trade_id = position["id"]
        if action.zero_proceeds:
            tokens_to_sell = position["tokens_remaining"]
            exec_p = 0.0
            slippage = 1.0
            gross = 0.0
            fee = 0.0
            net = 0.0
        else:
            if self.rng.random() < paper.sell_failed_tx_rate:
                await self._log("warning", "trade", f"Sell transaction failed for ${position['symbol']} — will retry")
                return None
            if action.sell_all:
                tokens_to_sell = position["tokens_remaining"]
            else:
                tokens_to_sell = min(position["tokens_remaining"], position["token_amount"] * action.fraction_of_original)
            if tokens_to_sell <= 0:
                return None
            price = max(float(position.get("current_price") or 0.0), 0.0)
            if price <= 0:
                tokens_to_sell = position["tokens_remaining"]
                exec_p = 0.0
                slippage = 1.0
                gross = 0.0
                fee = 0.0
                net = 0.0
            else:
                notional = tokens_to_sell * price
                liquidity = float(position.get("liquidity_now") or position.get("liquidity_at_entry") or 0.0)
                slippage = execution_slippage(notional, liquidity, self.rng, paper)
                exec_p = execution_price(price, slippage, "sell")
                gross = tokens_to_sell * exec_p
                fee = fee_usd(gross, paper, self.sol_price_getter())
                net = max(0.0, gross - fee)

        self.cash += net
        self.total_fees += fee
        position["tokens_remaining"] = max(0.0, position["tokens_remaining"] - tokens_to_sell)
        position["proceeds_usd"] += net
        position["fees_usd"] += fee
        sold = position["sold_tokens"] + tokens_to_sell
        position["sold_tokens"] = sold
        position["slip_sum"] += (slippage * 100) * tokens_to_sell
        position["exit_price_sum"] += exec_p * tokens_to_sell
        position["slip_weight"] = sold if sold > 0 else 1.0

        fill = {
            "ts": iso(utcnow()),
            "kind": action.kind,
            "reason": action.reason,
            "tokens": tokens_to_sell,
            "price": exec_p,
            "slippage_pct": round(slippage * 100, 3),
            "fee_usd": round(fee, 4),
            "proceeds_usd": round(net, 4),
            "zeroed": action.zero_proceeds,
        }
        position["fills"].append(fill)
        if action.activates_trailing:
            position["trailing_active"] = True
        if action.tp_index is not None and action.tp_index not in position["tp_taken"]:
            position["tp_taken"].append(action.tp_index)
        if action.zero_proceeds:
            position["tokens_remaining"] = 0.0
            position["rugged"] = True

        remaining = position["tokens_remaining"]
        closing = action.sell_all or remaining <= max(1e-12, position["token_amount"] * 1e-6)
        if closing:
            position["tokens_remaining"] = 0.0
        avg_exit = position["exit_price_sum"] / position["slip_weight"] if position["slip_weight"] > 0 else 0.0
        avg_slip = position["slip_sum"] / position["slip_weight"] if position["slip_weight"] > 0 else 0.0

        async with self.session_factory() as session:
            trade = await session.get(Trade, trade_id)
            if trade is None:
                self.positions.pop(trade_id, None)
                return None
            trade.tokens_remaining = 0.0 if closing else remaining
            trade.proceeds_usd = position["proceeds_usd"]
            trade.realized_partial = position["proceeds_usd"]
            trade.fees_usd = position["fees_usd"]
            trade.fills = position["fills"]
            trade.tp_taken = position["tp_taken"]
            trade.trailing_active = position["trailing_active"]
            trade.slippage_sell_pct = round(avg_slip, 3)
            trade.exit_price = avg_exit
            trade.peak_price = position["peak_price"]
            trade.peak_gain_pct = round((position["peak_price"] / trade.entry_price - 1) * 100, 2) if trade.entry_price else 0.0
            if position["trailing_active"] and position["peak_price"] > 0:
                trade.trailing_stop_price = position["peak_price"] * (1.0 - config.strategy.exits.trailing_stop_pct)

            result: dict[str, Any] = {}
            if closing:
                trade.status = "closed"
                trade.closed_at = utcnow()
                trade.token_amount = trade.token_amount
                trade.pnl_usd = trade.proceeds_usd - trade.size_usd
                trade.pnl_pct = (trade.pnl_usd / trade.size_usd * 100) if trade.size_usd else 0.0
                trade.hold_seconds = int((trade.closed_at - trade.opened_at).total_seconds())
                trade.exit_reasons = list(trade.exit_reasons or []) + [action.reason]
                trade.equity_after = self._wallet_sync()["equity"]
                self.realized_pnl += trade.pnl_usd
                self.trades_closed += 1
                if trade.pnl_usd > 0:
                    self.win_streak += 1
                    self.loss_streak = 0
                else:
                    self.loss_streak += 1
                    self.win_streak = 0
                result = trade_dict(trade)
            else:
                trade.equity_after = self._wallet_sync()["equity"]
                result = trade_dict(trade)
            await session.commit()

        if closing:
            self.positions.pop(trade_id, None)
            pnl = result["pnl_usd"]
            pnl_pct = result["pnl_pct"]
            await self._log(
                "trade" if pnl >= 0 else "warning",
                "trade",
                f"Closed ${position['symbol']} — PnL ${pnl:+,.2f} ({pnl_pct:+.1f}%) — {action.reason}",
                {"trade_id": trade_id, "mint": position["mint"], "pnl": pnl},
            )
            await self._notify("sell", f"{'🟢' if pnl >= 0 else '🔴'} Closed ${position['symbol']} ${pnl:+,.2f} ({pnl_pct:+.1f}%) — {action.reason}")
            if pnl >= config.notifier.big_win_usd:
                await self._notify("big_win", f"🚀 Big win: ${position['symbol']} +${pnl:,.2f} ({pnl_pct:+.1f}%)")
            await self.bus.broadcast({"type": "event", "payload": {"kind": "trade", "action": "close", "data": result}})
        else:
            await self._log(
                "trade",
                "trade",
                f"Sold part of ${position['symbol']} — {action.reason} — ${net:,.2f} proceeds",
                {"trade_id": trade_id, "mint": position["mint"], "proceeds": net},
            )
            await self.bus.broadcast({"type": "event", "payload": {"kind": "trade", "action": "partial", "data": result}})

        await self._save_account()
        await self.record_equity()
        wallet = self._wallet_sync()
        if wallet["equity"] < self.day_start_equity * (1 - config.strategy.circuit_breaker.daily_loss_limit_pct):
            if self.breaker_reason and not self.breaker_announced:
                self.breaker_announced = True
                await self._log("error", "risk", self.breaker_reason)
                await self._notify("breaker", f"⚠️ Circuit breaker: {self.breaker_reason}")
        return result

    async def manage_tick(self, prices: dict[str, dict[str, Any]], allow_exits: bool = True) -> None:
        if not self.positions or not prices:
            return
        config = self.get_config()
        async with self.lock:
            for trade_id, position in list(self.positions.items()):
                tick = prices.get(position["mint"])
                if not tick:
                    continue
                price = float(tick.get("price") or 0.0)
                if price > 0:
                    position["current_price"] = price
                    position["peak_price"] = max(position["peak_price"], price)
                if tick.get("liquidity") is not None:
                    position["liquidity_now"] = float(tick["liquidity"])
                if tick.get("market_cap") is not None:
                    position["current_market_cap"] = float(tick["market_cap"])
                position["creator_sold"] = bool(tick.get("creator_sold", position.get("creator_sold")))
                position["top_holders_dump"] = bool(tick.get("top_holders_dump", position.get("top_holders_dump")))
                if tick.get("rugged"):
                    position["rugged"] = True
                if not allow_exits:
                    continue
                plan = evaluate_exit(
                    {
                        **position,
                        "tp_taken": position["tp_taken"],
                        "trailing_active": position["trailing_active"],
                    },
                    config.strategy,
                    utcnow(),
                    {
                        "rugged": bool(position.get("rugged")),
                        "creator_sold": position.get("creator_sold"),
                        "top_holders_dump": position.get("top_holders_dump"),
                        "liquidity_usd": position.get("liquidity_now"),
                    },
                )
                if not plan.has_actions:
                    continue
                for action in plan.actions:
                    if trade_id not in self.positions:
                        break
                    await self._sell(position, action=action)

    async def close_position(self, trade_id: int, reason: str = "Manual close by operator") -> dict[str, Any] | None:
        async with self.lock:
            position = self.positions.get(trade_id)
            if position is None:
                return None
            action = ExitAction("manual", reason, sell_all=True)
            return await self._sell(position, action=action)

    # ── reset ─────────────────────────────────────────────────────
    async def reset(self) -> None:
        async with self.lock:
            async with self.session_factory() as session:
                await session.execute(delete(Trade))
                await session.execute(delete(EquityPoint))
                await session.commit()
            self.positions.clear()
            self.cash = self.starting_balance
            self.realized_pnl = 0.0
            self.total_fees = 0.0
            self.win_streak = 0
            self.loss_streak = 0
            self.trades_closed = 0
            self.day_key = utcnow().date().isoformat()
            self.day_start_equity = self.starting_balance
            self.breaker_reason = None
            self.breaker_announced = False
            await self._save_account()
            await self.record_equity()
        await self._log("info", "paper", f"Paper account reset to ${self.starting_balance:,.2f}")
        await self.bus.broadcast({"type": "event", "payload": {"kind": "account_reset", "data": {"balance": self.starting_balance}}})

    # ── views ─────────────────────────────────────────────────────
    def positions_view(self) -> list[dict[str, Any]]:
        config = self.get_config()
        exits = config.strategy.exits
        out: list[dict[str, Any]] = []
        for position in self.positions.values():
            entry = position["entry_price"]
            current = position.get("current_price") or entry
            size = position["size_usd"]
            remaining_ratio = position["tokens_remaining"] / max(position["token_amount"], 1e-12)
            value = position["tokens_remaining"] * current * (1 - config.paper.taker_fee_pct)
            basis = size * remaining_ratio
            unrealized = value - basis
            unrealized_pct = (unrealized / basis * 100) if basis > 0 else 0.0
            gain_pct = (current / entry - 1) * 100 if entry else 0.0
            stop_price = position["stop_price"]
            sl_span = max(entry - stop_price, 1e-12)
            sl_progress = clamp((entry - current) / sl_span, 0, 1)
            tp_levels = []
            next_tp_price = None
            next_tp_gain = None
            for index, level in enumerate(exits.take_profits):
                hit = index in position["tp_taken"]
                price_target = entry * (1 + level.gain_pct)
                tp_levels.append(
                    {
                        "index": index,
                        "gain_pct": level.gain_pct * 100,
                        "sell_fraction": level.sell_fraction,
                        "price": price_target,
                        "hit": hit,
                    }
                )
                if not hit and next_tp_price is None:
                    next_tp_price = price_target
                    next_tp_gain = level.gain_pct
            tp_progress = 0.0
            if next_tp_price and gain_pct >= 0:
                tp_progress = clamp((current - entry) / max(next_tp_price - entry, 1e-12), 0, 1)
            hold_seconds = int((utcnow() - position["opened_at"]).total_seconds())
            out.append(
                {
                    "id": position["id"],
                    "mint": position["mint"],
                    "name": position["name"],
                    "symbol": position["symbol"],
                    "image_url": position["image_url"],
                    "entry_price": entry,
                    "current_price": current,
                    "size_usd": round(size, 2),
                    "value_usd": round(value, 2),
                    "tokens_remaining": position["tokens_remaining"],
                    "remaining_ratio": round(remaining_ratio, 4),
                    "pnl_usd": round(unrealized, 2),
                    "pnl_pct": round(unrealized_pct, 2),
                    "gain_pct": round(gain_pct, 2),
                    "market_cap_at_entry": round(position.get("market_cap_at_entry", 0.0) or 0.0, 2),
                    "current_market_cap": round(position.get("current_market_cap", 0.0) or 0.0, 2),
                    "peak_price": position["peak_price"],
                    "peak_gain_pct": round((position["peak_price"] / entry - 1) * 100, 2) if entry else 0.0,
                    "stop_price": stop_price,
                    "sl_progress": round(sl_progress, 4),
                    "next_tp_price": next_tp_price,
                    "next_tp_gain_pct": (next_tp_gain * 100) if next_tp_gain is not None else None,
                    "tp_progress": round(tp_progress, 4),
                    "tp_levels": tp_levels,
                    "trailing_active": position["trailing_active"],
                    "trailing_stop_price": position["trailing_stop_price"],
                    "liquidity_usd": position.get("liquidity_now"),
                    "score": position["score"],
                    "safety": position["safety"],
                    "opportunity": position["opportunity"],
                    "opened_at": iso(position["opened_at"]),
                    "hold_seconds": hold_seconds,
                    "is_demo": position["is_demo"],
                }
            )
        out.sort(key=lambda item: item["opened_at"] or "", reverse=True)
        return out

    def open_mints(self) -> list[str]:
        return [position["mint"] for position in self.positions.values()]

    # ── helpers ───────────────────────────────────────────────────
    async def _log(self, level: str, category: str, message: str, meta: dict[str, Any] | None = None) -> None:
        await self.log_cb(level, category, message, meta)

    async def _notify(self, kind: str, message: str) -> None:
        await self.notify_cb(kind, message)

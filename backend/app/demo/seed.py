from __future__ import annotations

import asyncio
import logging
import math
import random
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select

from app.analyzer.checks import liquidity_score
from app.analyzer.scoring import score_token
from app.config import AppConfig
from app.db.models import EquityPoint, LogEntry, Setting, Token, Trade
from app.db.session import SessionLocal
from app.demo.generator import DemoGenerator
from app.utils import iso, utcnow

log = logging.getLogger("memeradar.seed")


def _make_price_path(rng: random.Random, start: float, peak_gain: float, end_gain: float, created: datetime) -> list[dict[str, Any]]:
    points = 90
    peak_index = rng.randint(int(points * 0.2), int(points * 0.75))
    peak = start * (1 + peak_gain)
    end = start * (1 + end_gain)
    path: list[dict[str, Any]] = []
    for index in range(points):
        fraction = index / (points - 1)
        if index <= peak_index:
            target = start + (peak - start) * (fraction / max(1e-6, peak_index / (points - 1)))
        else:
            portion = (fraction - peak_index / (points - 1)) / max(1e-6, 1 - peak_index / (points - 1))
            target = peak + (end - peak) * portion
        noise = 1.0 + rng.gauss(0.0, 0.035)
        price = max(1e-12, target * noise)
        path.append({"t": int((created + timedelta(seconds=index * 25)).timestamp()), "p": price})
    path[0]["p"] = start
    if 0 <= peak_index < points:
        path[peak_index]["p"] = max(path[peak_index]["p"], peak)
    path[-1]["p"] = end
    return path


async def seed_demo_data(config: AppConfig, force: bool = False) -> dict[str, Any]:
    async with SessionLocal() as session:
        count = (await session.execute(select(func.count(Token.id)))).scalar_one()
        if count and not force:
            return {"seeded": False, "reason": "database already has tokens"}

    rng = random.Random(42)
    generator = DemoGenerator(rng)
    now = utcnow()
    today_start = datetime(now.year, now.month, now.day)
    tokens: list[Token] = []
    token_outcomes: list[dict[str, Any]] = []
    created_times = sorted(now - timedelta(minutes=rng.uniform(15, 60 * 30)) for _ in range(110))

    for index, created in enumerate(created_times):
        draft = generator.next_token()
        draft.created_at = created
        profile = draft.demo_profile or {}
        checks = profile["checks"]
        opp = profile["opportunity"]
        hard = profile["hard"]
        scores = score_token(checks, opp, config.strategy, hard)
        archetype = draft.archetype or "solid"

        if archetype == "gem":
            peak_gain = rng.uniform(0.4, 5.5)
        elif archetype == "solid":
            peak_gain = rng.uniform(-0.35, 2.2) if rng.random() < 0.7 else rng.uniform(2.5, 11.0)
        elif archetype == "risky":
            roll = rng.random()
            peak_gain = rng.uniform(2.0, 18.0) if roll < 0.22 else (rng.uniform(-0.8, 1.2) if roll < 0.8 else rng.uniform(-0.95, -0.55))
        else:
            peak_gain = rng.uniform(0.5, 4.0) if rng.random() < 0.05 else rng.uniform(-0.98, -0.65)

        rugged = bool(scores.hard_rejected) or peak_gain <= -0.6 or (scores.verdict == "AVOID" and rng.random() < 0.25)
        end_gain = peak_gain
        if rugged:
            end_gain = rng.uniform(-0.99, -0.55)
        else:
            end_gain = peak_gain * rng.uniform(0.25, 0.9)

        path = _make_price_path(rng, draft.price_usd, peak_gain, end_gain, created + timedelta(minutes=1))
        final_price = path[-1]["p"]
        peak_price = max(point["p"] for point in path)
        liquidity_final = draft.liquidity_usd * (0.15 if rugged else rng.uniform(0.6, 1.8))
        market_cap = final_price * generator.supply

        decision = None
        decision_reason = None
        if scores.verdict == "BUY":
            decision = "BUY"
            decision_reason = f"BUY — score {scores.final_score:.0f} — " + (scores.green_flags[0] if scores.green_flags else "passed all checks")
        else:
            decision = "SKIP"
            decision_reason = f"{scores.verdict} — score {scores.final_score:.0f} — " + (
                scores.reject_reasons[0] if scores.reject_reasons else (scores.red_flags[0] if scores.red_flags else "below threshold")
            )

        token = Token(
            mint=draft.mint,
            name=draft.name,
            symbol=draft.symbol,
            creator=draft.creator,
            source=draft.source,
            created_at=created,
            detected_at=created,
            image_url=draft.image_url,
            website=draft.website,
            twitter=draft.twitter,
            telegram=draft.telegram,
            initial_price_usd=draft.price_usd,
            initial_market_cap_usd=draft.market_cap_usd,
            initial_liquidity_usd=draft.liquidity_usd,
            price_usd=final_price,
            market_cap_usd=market_cap,
            liquidity_usd=liquidity_final,
            peak_price_usd=peak_price,
            safety_score=scores.safety_score,
            opportunity_score=scores.opportunity_score,
            final_score=scores.final_score,
            verdict=scores.verdict,
            hard_rejected=scores.hard_rejected,
            red_flags=scores.red_flags,
            green_flags=scores.green_flags,
            rejected_reasons=scores.reject_reasons,
            checks=checks,
            opportunity_metrics=opp,
            score_breakdown=scores.breakdown,
            decision=decision,
            decision_reason=decision_reason,
            price_history=path,
            rugged=rugged,
            peak_gain_pct=round((peak_price / draft.price_usd - 1) * 100, 2),
            is_demo=True,
        )
        tokens.append(token)
        token_outcomes.append(
            {
                "token": token,
                "peak_gain": (peak_price / draft.price_usd - 1),
                "rugged": rugged,
                "created": created,
                "buy": scores.verdict == "BUY",
                "score": scores.final_score,
                "safety": scores.safety_score,
                "opportunity": scores.opportunity_score,
                "green": scores.green_flags,
            }
        )

    non_rugged = [item for item in token_outcomes if not item["rugged"]]
    rugged_pool = [item for item in token_outcomes if item["rugged"] and item["buy"]]
    rng.shuffle(rugged_pool)
    preferred = [item for item in non_rugged if item["buy"]]
    fallback = [item for item in non_rugged if not item["buy"]]
    rng.shuffle(preferred)
    rng.shuffle(fallback)
    candidates = rugged_pool[:2] + preferred[:14]
    if len(candidates) < 16:
        candidates += fallback[: 16 - len(candidates)]
    rng.shuffle(candidates)
    chosen = candidates[:16]
    chosen.sort(key=lambda item: item["created"])

    equity = config.paper.starting_balance
    trades: list[Trade] = []
    realized_events: list[tuple[datetime, float]] = []
    last_results: list[int] = []
    for item in chosen:
        token: Token = item["token"]
        size = round(rng.uniform(2.2, 7.8), 2)
        win = (not item["rugged"]) and item["peak_gain"] >= 0.15 and rng.random() < 0.55
        if win:
            pnl_pct = min(item["peak_gain"] * rng.uniform(0.25, 0.55), 4.2) * 100
            pnl_pct = max(12.0, pnl_pct)
            exit_reason = f"Take profit stage 1 at +{pnl_pct:.0f}%"
        else:
            pnl_pct = -100.0 if item["rugged"] else rng.uniform(-28, -8)
            exit_reason = "Token rugged — liquidity gone, position wiped out" if item["rugged"] else f"Stop loss hit at {pnl_pct:.1f}%"
        pnl = round(size * pnl_pct / 100, 2)
        opened = item["created"] + timedelta(minutes=rng.uniform(1, 4))
        hold = int(rng.uniform(180, 3600))
        closed = min(now - timedelta(minutes=2), opened + timedelta(seconds=hold))
        slippage_buy = rng.uniform(1.2, 5.5)
        slippage_sell = rng.uniform(1.5, 7.0)
        fees = round(size * config.paper.taker_fee_pct + rng.uniform(0.05, 0.35), 2)
        entry_price = token.initial_price_usd * (1 + slippage_buy / 100)
        exit_price = entry_price * (1 + pnl_pct / 100)
        equity += pnl
        realized_events.append((closed, pnl))
        last_results.append(1 if pnl > 0 else 0)
        token.trade_id = None
        trades.append(
            Trade(
                token_mint=token.mint,
                token_name=token.name,
                symbol=token.symbol,
                image_url=token.image_url,
                status="closed",
                opened_at=opened,
                closed_at=closed,
                entry_price=entry_price,
                exit_price=exit_price,
                size_usd=size,
                token_amount=size / entry_price,
                tokens_remaining=0.0,
                proceeds_usd=size + pnl,
                realized_partial=size + pnl,
                liquidity_at_entry=token.initial_liquidity_usd,
                peak_price=max(token.peak_price_usd, entry_price * (1 + max(pnl_pct, 0) / 100)),
                score_at_entry=item["score"],
                safety_at_entry=item["safety"],
                opportunity_at_entry=item["opportunity"],
                buy_reasons=[
                    f"Final score {item['score']:.1f}",
                    *item["green"][:3],
                ],
                exit_reasons=[exit_reason],
                sizing={"seeded": True},
                fills=[],
                tp_taken=[0] if win else [],
                trailing_active=win,
                slippage_buy_pct=round(slippage_buy, 2),
                slippage_sell_pct=round(slippage_sell, 2),
                fees_usd=fees,
                pnl_usd=pnl,
                pnl_pct=round(pnl_pct, 2),
                peak_gain_pct=round(item["peak_gain"] * 100, 2),
                hold_seconds=hold,
                equity_after=round(equity, 2),
                is_demo=True,
            )
        )

    total_pnl = sum(trade.pnl_usd for trade in trades)
    final_equity = config.paper.starting_balance + total_pnl
    day_start_equity = config.paper.starting_balance + sum(
        trade.pnl_usd for trade in trades if trade.closed_at and trade.closed_at < today_start
    )

    win_streak = 0
    loss_streak = 0
    for result in reversed(last_results):
        if result == 1:
            if loss_streak:
                break
            win_streak += 1
        else:
            if win_streak:
                break
            loss_streak += 1

    equity_points: list[EquityPoint] = []
    curve_start = created_times[0] - timedelta(hours=1)
    steps = 90
    for step in range(steps + 1):
        ts = curve_start + (now - curve_start) * (step / steps)
        realized = sum(pnl for closed, pnl in realized_events if closed <= ts)
        value = config.paper.starting_balance + realized
        if step < steps:
            value += rng.uniform(-0.25, 0.25)
        cash_estimate = value - rng.uniform(0, max(0.0, value * 0.35))
        equity_points.append(
            EquityPoint(
                ts=ts,
                equity=round(value, 2),
                cash=round(cash_estimate, 2),
                open_value=round(value - cash_estimate, 2),
                realized_pnl=round(realized, 2),
                unrealized_pnl=round(value - config.paper.starting_balance - realized, 2),
            )
        )
    equity_points.append(
        EquityPoint(
            ts=now,
            equity=round(final_equity, 2),
            cash=round(final_equity, 2),
            open_value=0.0,
            realized_pnl=round(total_pnl, 2),
            unrealized_pnl=0.0,
        )
    )

    logs: list[LogEntry] = [
        LogEntry(
            ts=curve_start,
            level="info",
            category="system",
            message=f"MemeRadar demo dataset seeded — {len(tokens)} tokens, {len(trades)} historical paper trades",
        )
    ]
    for trade in trades[:20]:
        logs.append(
            LogEntry(
                ts=trade.opened_at,
                level="trade",
                category="trade",
                message=f"Bought ${trade.size_usd:,.2f} of ${trade.symbol} at ${trade.entry_price:.8f} — score {trade.score_at_entry:.0f}",
                meta={"trade_id": trade.id, "mint": trade.token_mint, "seeded": True},
            )
        )
        logs.append(
            LogEntry(
                ts=trade.closed_at or trade.opened_at,
                level="trade" if trade.pnl_usd >= 0 else "warning",
                category="trade",
                message=f"Closed ${trade.symbol} — PnL ${trade.pnl_usd:+,.2f} ({trade.pnl_pct:+.1f}%) — {(trade.exit_reasons or [''])[0]}",
                meta={"trade_id": trade.id, "mint": trade.token_mint, "seeded": True},
            )
        )
    logs.sort(key=lambda entry: entry.ts)

    async with SessionLocal() as session:
        if force:
            await session.execute(delete(Trade))
            await session.execute(delete(EquityPoint))
            await session.execute(delete(Token))
            await session.execute(delete(LogEntry))
            await session.execute(delete(Setting).where(Setting.key == "account"))
            await session.commit()
        for token in tokens:
            session.add(token)
        await session.flush()
        traded_mints = {trade.token_mint for trade in trades}
        for token in tokens:
            if token.mint in traded_mints:
                token.decision = "BUY"
        for trade in trades:
            session.add(trade)
        await session.flush()
        for trade in trades:
            for token in tokens:
                if token.mint == trade.token_mint:
                    token.trade_id = trade.id
        for point in equity_points:
            session.add(point)
        for entry in logs:
            session.add(entry)
        account = {
            "starting_balance": config.paper.starting_balance,
            "cash": round(final_equity, 6),
            "win_streak": win_streak,
            "loss_streak": loss_streak,
            "day_key": now.date().isoformat(),
            "day_start_equity": round(day_start_equity, 6),
            "updated_at": iso(now),
        }
        session.add(Setting(key="account", value=account, updated_at=now))
        await session.commit()

    return {
        "seeded": True,
        "tokens": len(tokens),
        "trades": len(trades),
        "equity": round(final_equity, 2),
        "win_rate": round(sum(1 for trade in trades if trade.pnl_usd > 0) / len(trades) * 100, 1) if trades else 0,
    }


async def main() -> None:
    from app.config import build_config
    from app.db.session import init_db

    logging.basicConfig(level=logging.INFO)
    await init_db()
    config = build_config()
    result = await seed_demo_data(config, force=True)
    log.info("Seed result: %s", result)


if __name__ == "__main__":
    asyncio.run(main())

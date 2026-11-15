from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

from app.analyzer.scoring import score_token
from app.config import AppConfig, build_config, deep_merge
from app.db.models import Token
from app.paper_engine.slippage import amm_slippage, fee_usd
from app.strategy.exits import evaluate_exit
from app.utils import clamp


def _hard_from_checks(checks: dict[str, Any]) -> dict[str, Any]:
    holders = (checks.get("holders") or {}).get("data") or {}
    creator = (checks.get("creator") or {}).get("data") or {}
    liquidity = (checks.get("liquidity") or {}).get("data") or {}
    honeypot = (checks.get("honeypot") or {}).get("data") or {}
    return {
        "mint_authority_revoked": (checks.get("mint_authority") or {}).get("passed"),
        "freeze_authority_revoked": (checks.get("freeze_authority") or {}).get("passed"),
        "honeypot": honeypot.get("detected"),
        "top10_pct": float(holders.get("top10_pct") or 0.0),
        "top1_pct": float(holders.get("top1_pct") or 0.0),
        "liquidity_usd": float(liquidity.get("usd") or 0.0),
        "holders": int(holders.get("count") or 0),
        "creator_rugs": int(creator.get("previous_rugs") or 0),
    }


def run_backtest(tokens: list[Token], config: AppConfig, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Replay stored tokens through the current scoring + exit rules."""
    if overrides:
        merged = deep_merge(config.model_dump(), overrides)
        config = build_config(merged)
    rng = random.Random(1337)
    starting = config.paper.starting_balance
    cash = starting
    equity_curve: list[dict[str, Any]] = [{"t": (datetime.utcnow() - timedelta(hours=24)).isoformat() + "Z", "equity": starting}]
    trades: list[dict[str, Any]] = []
    avoided = 0
    missed = 0
    dodged = 0
    rugged_tokens = 0

    ordered = sorted(tokens, key=lambda token: token.created_at)
    for token in ordered:
        if not token.checks:
            continue
        scores = score_token(token.checks, token.opportunity_metrics or {}, config.strategy, _hard_from_checks(token.checks))
        if token.rugged:
            rugged_tokens += 1
        if scores.verdict != "BUY":
            avoided += 1
            if token.peak_gain_pct >= 900:
                missed += 1
            if token.rugged:
                dodged += 1
            continue

        history = token.price_history or []
        if not history:
            history = [{"t": int(token.created_at.timestamp()), "p": token.initial_price_usd or token.price_usd}]
        entry = float(history[0].get("p") or token.initial_price_usd or token.price_usd or 1e-9)
        if entry <= 0:
            continue
        liquidity = token.initial_liquidity_usd or token.liquidity_usd or 0.0
        equity_now = cash
        size = clamp(equity_now * config.paper.base_pct if hasattr(config.paper, "base_pct") else equity_now * config.strategy.sizing.base_pct_of_equity, 0.0, equity_now * config.paper.max_position_pct)
        if liquidity > 0:
            size = min(size, liquidity * config.paper.max_pool_share_pct)
        if size < config.paper.min_trade_usd:
            continue
        buy_slip = amm_slippage(size, liquidity) + config.paper.random_slippage_min_pct
        buy_price = entry * (1 + buy_slip)
        buy_fee = fee_usd(size, config.paper, config.app.sol_price_usd)
        tokens_held = max(0.0, (size - buy_fee) / buy_price)
        position = {
            "entry_price": buy_price,
            "current_price": buy_price,
            "peak_price": buy_price,
            "tokens_remaining": tokens_held,
            "token_amount": tokens_held,
            "liquidity_at_entry": liquidity,
            "liquidity_now": liquidity,
            "tp_taken": [],
            "trailing_active": False,
            "opened_at": token.created_at,
            "size_usd": size,
        }
        proceeds = 0.0
        sold = 0.0
        exit_reasons: list[str] = []
        exit_time = None
        for point in history:
            price = float(point.get("p") or 0.0)
            if price <= 0:
                continue
            ts = datetime.utcfromtimestamp(float(point.get("t") or token.created_at.timestamp()))
            position["current_price"] = price
            position["peak_price"] = max(position["peak_price"], price)
            position["liquidity_now"] = max(50.0, liquidity * (price / entry) ** 0.6)
            plan = evaluate_exit(position, config.strategy, ts, {"liquidity_usd": position["liquidity_now"], "rugged": token.rugged})
            for action in plan.actions:
                if action.zero_proceeds:
                    exit_reasons.append(action.reason)
                    position["tokens_remaining"] = 0.0
                    sold = tokens_held
                    exit_time = ts
                    break
                qty = position["tokens_remaining"] if action.sell_all else min(position["tokens_remaining"], tokens_held * action.fraction_of_original)
                if qty <= 0:
                    continue
                slip = amm_slippage(qty * price, position["liquidity_now"]) + config.paper.random_slippage_max_pct
                exec_price = price * max(0.01, 1 - slip)
                gross = qty * exec_price
                net = max(0.0, gross - fee_usd(gross, config.paper, config.app.sol_price_usd))
                proceeds += net
                sold += qty
                position["tokens_remaining"] -= qty
                if action.activates_trailing:
                    position["trailing_active"] = True
                if action.tp_index is not None:
                    position["tp_taken"].append(action.tp_index)
                exit_reasons.append(action.reason)
                if action.sell_all or position["tokens_remaining"] <= tokens_held * 1e-6:
                    position["tokens_remaining"] = 0.0
                    exit_time = ts
                    break
            if position["tokens_remaining"] <= 0:
                break
        if position["tokens_remaining"] > 0:
            last_price = float(history[-1].get("p") or entry)
            qty = position["tokens_remaining"]
            slip = amm_slippage(qty * last_price, max(position["liquidity_now"], 100.0)) + config.paper.random_slippage_min_pct
            gross = qty * last_price * max(0.01, 1 - slip)
            proceeds += max(0.0, gross - fee_usd(gross, config.paper, config.app.sol_price_usd))
            sold += qty
            position["tokens_remaining"] = 0.0
            exit_time = datetime.utcfromtimestamp(float(history[-1].get("t") or token.created_at.timestamp()))
            exit_reasons.append("Backtest end — marked to market")

        pnl = proceeds - size
        cash += pnl
        pnl_pct = pnl / size * 100 if size else 0.0
        trades.append(
            {
                "mint": token.mint,
                "symbol": token.symbol,
                "score": scores.final_score,
                "safety": scores.safety_score,
                "opportunity": scores.opportunity_score,
                "size_usd": round(size, 2),
                "entry_price": buy_price,
                "pnl_usd": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "exit_reasons": exit_reasons,
                "opened_at": token.created_at.isoformat() + "Z",
                "closed_at": (exit_time.isoformat() + "Z") if exit_time else None,
            }
        )
        equity_curve.append(
            {
                "t": (exit_time.isoformat() + "Z") if exit_time else token.created_at.isoformat() + "Z",
                "equity": round(starting + sum(item["pnl_usd"] for item in trades), 2),
            }
        )

    wins = [trade for trade in trades if trade["pnl_usd"] > 0]
    losses = [trade for trade in trades if trade["pnl_usd"] <= 0]
    gross_win = sum(trade["pnl_usd"] for trade in wins)
    gross_loss = abs(sum(trade["pnl_usd"] for trade in losses))
    peak = starting
    max_dd = 0.0
    for point in equity_curve:
        peak = max(peak, point["equity"])
        max_dd = max(max_dd, (peak - point["equity"]) / peak if peak else 0.0)
    final_equity = starting + sum(trade["pnl_usd"] for trade in trades)
    return {
        "trades": trades,
        "equity_curve": equity_curve,
        "scanned": len(ordered),
        "bought": len(trades),
        "avoided": avoided,
        "missed_opportunities": missed,
        "bullets_dodged": dodged,
        "rugged_tokens": rugged_tokens,
        "metrics": {
            "starting_balance": starting,
            "final_equity": round(final_equity, 2),
            "pnl": round(final_equity - starting, 2),
            "roi_pct": round((final_equity - starting) / starting * 100, 2) if starting else 0.0,
            "win_rate": round(len(wins) / len(trades) * 100, 2) if trades else 0.0,
            "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else (99.0 if gross_win else 0.0),
            "max_drawdown": round(max_dd * 100, 2),
            "avg_trade_pct": round(sum(trade["pnl_pct"] for trade in trades) / len(trades), 2) if trades else 0.0,
        },
        "config": {
            "min_score_buy": config.strategy.min_score_buy,
            "safety_weight": config.strategy.safety_weight,
            "opportunity_weight": config.strategy.opportunity_weight,
            "stop_loss_pct": config.strategy.exits.stop_loss_pct,
        },
    }

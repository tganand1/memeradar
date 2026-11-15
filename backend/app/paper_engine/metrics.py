from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from typing import Any

from app.db.models import EquityPoint, Token, Trade
from app.utils import iso


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b else default


def compute_metrics(
    trades: list[Trade],
    equity_points: list[EquityPoint],
    starting_balance: float,
    current_equity: float,
) -> dict[str, Any]:
    closed = [trade for trade in trades if trade.status == "closed"]
    pnls = [trade.pnl_usd for trade in closed]
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    returns = [(trade.pnl_pct / 100.0) for trade in closed]

    sharpe = 0.0
    if len(returns) >= 3:
        mean = sum(returns) / len(returns)
        variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
        std = math.sqrt(variance)
        if std > 0:
            sharpe = (mean / std) * math.sqrt(len(returns))

    peak = starting_balance
    max_drawdown = 0.0
    for point in equity_points:
        peak = max(peak, point.equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - point.equity) / peak)
    peak = max(peak, current_equity)
    if peak > 0:
        max_drawdown = max(max_drawdown, (peak - current_equity) / peak)

    best = max(closed, key=lambda trade: trade.pnl_usd, default=None)
    worst = min(closed, key=lambda trade: trade.pnl_usd, default=None)
    rugged = sum(
        1
        for trade in closed
        if any("rugged" in reason.lower() for reason in (trade.exit_reasons or [])) or trade.pnl_pct <= -95
    )
    avg_slippage_cost = sum(
        trade.size_usd * ((trade.slippage_buy_pct + trade.slippage_sell_pct) / 100.0) for trade in closed
    )
    hold = [trade.hold_seconds for trade in closed if trade.hold_seconds]

    return {
        "trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(closed) * 100, 2) if closed else 0.0,
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0.0,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0.0,
        "avg_pnl": round(sum(pnls) / len(pnls), 2) if pnls else 0.0,
        "avg_pnl_pct": round(sum(trade.pnl_pct for trade in closed) / len(closed), 2) if closed else 0.0,
        "gross_profit": round(gross_win, 2),
        "gross_loss": round(gross_loss, 2),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0),
        "expectancy": round(sum(pnls) / len(pnls), 2) if pnls else 0.0,
        "max_drawdown": round(max_drawdown * 100, 2),
        "sharpe": round(sharpe, 2),
        "best_trade": {
            "symbol": best.symbol,
            "pnl_usd": round(best.pnl_usd, 2),
            "pnl_pct": round(best.pnl_pct, 2),
            "id": best.id,
        }
        if best
        else None,
        "worst_trade": {
            "symbol": worst.symbol,
            "pnl_usd": round(worst.pnl_usd, 2),
            "pnl_pct": round(worst.pnl_pct, 2),
            "id": worst.id,
        }
        if worst
        else None,
        "avg_hold_seconds": int(sum(hold) / len(hold)) if hold else 0,
        "rug_count": rugged,
        "avg_slippage_cost": round(avg_slippage_cost, 2),
        "total_fees": round(sum(trade.fees_usd for trade in closed), 2),
        "total_pnl": round(sum(pnls), 2),
        "roi_pct": round((current_equity - starting_balance) / starting_balance * 100, 2) if starting_balance else 0.0,
    }


def _bucket(score: float) -> str:
    low = int(score // 10 * 10)
    low = max(0, min(90, low))
    return f"{low}-{low + 10}"


def compute_analytics(closed_trades: list[Trade], tokens: list[Token]) -> dict[str, Any]:
    token_map = {token.mint: token for token in tokens}
    buckets: dict[str, dict[str, Any]] = {}
    hours: dict[int, dict[str, Any]] = {hour: {"hour": hour, "trades": 0, "wins": 0, "pnl": 0.0} for hour in range(24)}
    weekdays: dict[int, dict[str, Any]] = {day: {"weekday": day, "trades": 0, "wins": 0, "pnl": 0.0} for day in range(7)}
    heatmap: dict[tuple[int, int], dict[str, Any]] = defaultdict(lambda: {"trades": 0, "pnl": 0.0})
    filter_stats: dict[str, dict[str, Any]] = {}

    for trade in closed_trades:
        key = _bucket(trade.score_at_entry)
        bucket = buckets.setdefault(key, {"bucket": key, "trades": 0, "wins": 0, "pnl": 0.0, "pnl_pcts": []})
        bucket["trades"] += 1
        bucket["wins"] += 1 if trade.pnl_usd > 0 else 0
        bucket["pnl"] += trade.pnl_usd
        bucket["pnl_pcts"].append(trade.pnl_pct)

        opened: datetime = trade.opened_at
        hour_entry = hours[opened.hour]
        hour_entry["trades"] += 1
        hour_entry["wins"] += 1 if trade.pnl_usd > 0 else 0
        hour_entry["pnl"] += trade.pnl_usd
        weekday_entry = weekdays[opened.weekday()]
        weekday_entry["trades"] += 1
        weekday_entry["wins"] += 1 if trade.pnl_usd > 0 else 0
        weekday_entry["pnl"] += trade.pnl_usd
        cell = heatmap[(opened.weekday(), opened.hour)]
        cell["trades"] += 1
        cell["pnl"] += trade.pnl_usd

        token = token_map.get(trade.token_mint)
        if token and token.checks:
            for check_id, check in (token.checks or {}).items():
                entry = filter_stats.setdefault(
                    check_id,
                    {
                        "id": check_id,
                        "name": check.get("name", check_id),
                        "passed": {"trades": 0, "wins": 0, "pnl": 0.0},
                        "failed": {"trades": 0, "wins": 0, "pnl": 0.0},
                    },
                )
                side = "passed" if check.get("passed") else "failed"
                entry[side]["trades"] += 1
                entry[side]["wins"] += 1 if trade.pnl_usd > 0 else 0
                entry[side]["pnl"] += trade.pnl_usd

    score_buckets = []
    for key in sorted(buckets.keys(), key=lambda value: int(value.split("-")[0])):
        bucket = buckets[key]
        score_buckets.append(
            {
                "bucket": key,
                "trades": bucket["trades"],
                "wins": bucket["wins"],
                "win_rate": round(bucket["wins"] / bucket["trades"] * 100, 2) if bucket["trades"] else 0.0,
                "pnl": round(bucket["pnl"], 2),
                "avg_pnl_pct": round(sum(bucket["pnl_pcts"]) / len(bucket["pnl_pcts"]), 2) if bucket["pnl_pcts"] else 0.0,
            }
        )

    filters = []
    for entry in filter_stats.values():
        passed = entry["passed"]
        failed = entry["failed"]
        filters.append(
            {
                "id": entry["id"],
                "name": entry["name"],
                "passed_trades": passed["trades"],
                "passed_win_rate": round(passed["wins"] / passed["trades"] * 100, 2) if passed["trades"] else None,
                "passed_pnl": round(passed["pnl"], 2),
                "failed_trades": failed["trades"],
                "failed_win_rate": round(failed["wins"] / failed["trades"] * 100, 2) if failed["trades"] else None,
                "failed_pnl": round(failed["pnl"], 2),
            }
        )
    filters.sort(key=lambda item: item["passed_trades"] + item["failed_trades"], reverse=True)

    threshold_rows = []
    for threshold in (55, 60, 65, 70, 75, 80, 85, 90):
        selected = [trade for trade in closed_trades if trade.score_at_entry >= threshold]
        wins = sum(1 for trade in selected if trade.pnl_usd > 0)
        threshold_rows.append(
            {
                "threshold": threshold,
                "trades": len(selected),
                "win_rate": round(wins / len(selected) * 100, 2) if selected else 0.0,
                "pnl": round(sum(trade.pnl_usd for trade in selected), 2),
                "avg_pnl_pct": round(sum(trade.pnl_pct for trade in selected) / len(selected), 2) if selected else 0.0,
            }
        )

    rejected = [token for token in tokens if token.verdict != "BUY"]
    missed = [token for token in rejected if token.peak_gain_pct >= 900]
    dodged = [token for token in rejected if token.rugged or token.peak_gain_pct <= -80]

    heatmap_rows = [
        {"weekday": weekday, "hour": hour, "trades": cell["trades"], "pnl": round(cell["pnl"], 2)}
        for (weekday, hour), cell in sorted(heatmap.items())
    ]

    return {
        "score_buckets": score_buckets,
        "by_hour": [hours[hour] for hour in range(24)],
        "by_weekday": [weekdays[day] for day in range(7)],
        "heatmap": heatmap_rows,
        "filters": filters,
        "what_if": threshold_rows,
        "missed_opportunities": [
            {
                "mint": token.mint,
                "name": token.name,
                "symbol": token.symbol,
                "verdict": token.verdict,
                "final_score": token.final_score,
                "safety_score": token.safety_score,
                "opportunity_score": token.opportunity_score,
                "peak_gain_pct": token.peak_gain_pct,
                "initial_market_cap_usd": token.initial_market_cap_usd,
                "image_url": token.image_url,
                "created_at": iso(token.created_at),
                "reasons": (token.rejected_reasons or [])[:3],
            }
            for token in sorted(missed, key=lambda token: token.peak_gain_pct, reverse=True)[:25]
        ],
        "bullets_dodged": [
            {
                "mint": token.mint,
                "name": token.name,
                "symbol": token.symbol,
                "verdict": token.verdict,
                "final_score": token.final_score,
                "peak_gain_pct": token.peak_gain_pct,
                "rugged": token.rugged,
                "image_url": token.image_url,
                "created_at": iso(token.created_at),
                "reasons": (token.rejected_reasons or [])[:3],
            }
            for token in sorted(dodged, key=lambda token: token.peak_gain_pct)[:25]
        ],
        "counts": {
            "missed": len(missed),
            "dodged": len(dodged),
            "rejected": len(rejected),
            "scanned": len(tokens),
        },
    }

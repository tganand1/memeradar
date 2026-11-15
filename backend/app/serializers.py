from __future__ import annotations

from typing import Any

from app.db.models import LogEntry, Token, Trade
from app.utils import iso, utcnow


def trade_dict(trade: Trade) -> dict[str, Any]:
    return {
        "id": trade.id,
        "mint": trade.token_mint,
        "name": trade.token_name,
        "symbol": trade.symbol,
        "image_url": trade.image_url,
        "status": trade.status,
        "opened_at": iso(trade.opened_at),
        "closed_at": iso(trade.closed_at),
        "entry_price": trade.entry_price,
        "exit_price": round(trade.exit_price, 12),
        "size_usd": round(trade.size_usd, 2),
        "token_amount": trade.token_amount,
        "tokens_remaining": trade.tokens_remaining,
        "entry_market_cap_usd": round(trade.entry_market_cap_usd, 2),
        "proceeds_usd": round(trade.proceeds_usd, 2),
        "realized_partial": round(trade.realized_partial, 2),
        "liquidity_at_entry": round(trade.liquidity_at_entry, 2),
        "peak_price": trade.peak_price,
        "peak_gain_pct": trade.peak_gain_pct,
        "score_at_entry": trade.score_at_entry,
        "safety_at_entry": trade.safety_at_entry,
        "opportunity_at_entry": trade.opportunity_at_entry,
        "buy_reasons": trade.buy_reasons or [],
        "exit_reasons": trade.exit_reasons or [],
        "sizing": trade.sizing or {},
        "fills": trade.fills or [],
        "tp_taken": trade.tp_taken or [],
        "trailing_active": trade.trailing_active,
        "stop_price": trade.stop_price,
        "trailing_stop_price": trade.trailing_stop_price,
        "slippage_buy_pct": trade.slippage_buy_pct,
        "slippage_sell_pct": trade.slippage_sell_pct,
        "fees_usd": trade.fees_usd,
        "pnl_usd": round(trade.pnl_usd, 2),
        "pnl_pct": trade.pnl_pct,
        "hold_seconds": trade.hold_seconds,
        "equity_after": round(trade.equity_after, 2),
        "is_demo": trade.is_demo,
    }


def token_dict(token: Token, *, include_checks: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": token.id,
        "mint": token.mint,
        "name": token.name,
        "symbol": token.symbol,
        "creator": token.creator,
        "source": token.source,
        "created_at": iso(token.created_at),
        "detected_at": iso(token.detected_at),
        "image_url": token.image_url,
        "website": token.website,
        "twitter": token.twitter,
        "telegram": token.telegram,
        "initial_price_usd": token.initial_price_usd,
        "initial_market_cap_usd": token.initial_market_cap_usd,
        "initial_liquidity_usd": token.initial_liquidity_usd,
        "price_usd": token.price_usd,
        "market_cap_usd": token.market_cap_usd,
        "liquidity_usd": token.liquidity_usd,
        "peak_price_usd": token.peak_price_usd,
        "peak_gain_pct": token.peak_gain_pct,
        "safety_score": token.safety_score,
        "opportunity_score": token.opportunity_score,
        "final_score": token.final_score,
        "verdict": token.verdict,
        "hard_rejected": token.hard_rejected,
        "red_flags": token.red_flags or [],
        "green_flags": token.green_flags or [],
        "rejected_reasons": token.rejected_reasons or [],
        "opportunity_metrics": token.opportunity_metrics or {},
        "decision": token.decision,
        "decision_reason": token.decision_reason,
        "trade_id": token.trade_id,
        "rugged": token.rugged,
        "is_demo": token.is_demo,
        "last_updated_at": iso(token.last_updated_at),
    }
    if include_checks:
        data["checks"] = token.checks or {}
        data["score_breakdown"] = token.score_breakdown or {}
        data["price_history"] = token.price_history or []
    return data


def log_dict(entry: LogEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "ts": iso(entry.ts),
        "level": entry.level,
        "category": entry.category,
        "message": entry.message,
        "meta": entry.meta or {},
    }


def age_seconds(created_at) -> int:
    if not created_at:
        return 0
    return max(0, int((utcnow() - created_at).total_seconds()))

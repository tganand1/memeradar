from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils import utcnow


class Base(DeclarativeBase):
    pass


class Token(Base):
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    symbol: Mapped[str] = mapped_column(String(32), default="")
    creator: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    twitter: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram: Mapped[str | None] = mapped_column(Text, nullable=True)

    initial_price_usd: Mapped[float] = mapped_column(Float, default=0.0)
    initial_market_cap_usd: Mapped[float] = mapped_column(Float, default=0.0)
    initial_liquidity_usd: Mapped[float] = mapped_column(Float, default=0.0)
    price_usd: Mapped[float] = mapped_column(Float, default=0.0)
    market_cap_usd: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity_usd: Mapped[float] = mapped_column(Float, default=0.0)
    peak_price_usd: Mapped[float] = mapped_column(Float, default=0.0)

    safety_score: Mapped[float] = mapped_column(Float, default=0.0)
    opportunity_score: Mapped[float] = mapped_column(Float, default=0.0)
    final_score: Mapped[float] = mapped_column(Float, default=0.0)
    verdict: Mapped[str] = mapped_column(String(16), default="AVOID", index=True)
    hard_rejected: Mapped[bool] = mapped_column(Boolean, default=False)
    red_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    green_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    rejected_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    checks: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    opportunity_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    trade_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    price_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    rugged: Mapped[bool] = mapped_column(Boolean, default=False)
    peak_gain_pct: Mapped[float] = mapped_column(Float, default=0.0)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Skipped-token tracker ───────────────────────────────────────────
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    reject_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    skipped_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # ── Future price/liquidity tracking (DexScreener) ────────────────────
    price_5m: Mapped[float] = mapped_column(Float, default=0.0)
    price_15m: Mapped[float] = mapped_column(Float, default=0.0)
    price_1h: Mapped[float] = mapped_column(Float, default=0.0)
    price_4h: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity_5m: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity_15m: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity_1h: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity_4h: Mapped[float] = mapped_column(Float, default=0.0)
    is_real_runner: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_tokens_verdict_created", "verdict", "created_at"),
        Index("ix_tokens_hard_rejected", "hard_rejected"),
    )


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_mint: Mapped[str] = mapped_column(String(64), index=True)
    token_name: Mapped[str] = mapped_column(String(128), default="")
    symbol: Mapped[str] = mapped_column(String(32), default="")
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    entry_price: Mapped[float] = mapped_column(Float, default=0.0)
    exit_price: Mapped[float] = mapped_column(Float, default=0.0)
    size_usd: Mapped[float] = mapped_column(Float, default=0.0)
    token_amount: Mapped[float] = mapped_column(Float, default=0.0)
    tokens_remaining: Mapped[float] = mapped_column(Float, default=0.0)
    entry_market_cap_usd: Mapped[float] = mapped_column(Float, default=0.0)
    proceeds_usd: Mapped[float] = mapped_column(Float, default=0.0)
    realized_partial: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity_at_entry: Mapped[float] = mapped_column(Float, default=0.0)
    peak_price: Mapped[float] = mapped_column(Float, default=0.0)

    score_at_entry: Mapped[float] = mapped_column(Float, default=0.0)
    safety_at_entry: Mapped[float] = mapped_column(Float, default=0.0)
    opportunity_at_entry: Mapped[float] = mapped_column(Float, default=0.0)
    buy_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    exit_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    sizing: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    fills: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    tp_taken: Mapped[list[int]] = mapped_column(JSON, default=list)
    trailing_active: Mapped[bool] = mapped_column(Boolean, default=False)
    stop_price: Mapped[float] = mapped_column(Float, default=0.0)
    trailing_stop_price: Mapped[float] = mapped_column(Float, default=0.0)
    pending_sell: Mapped[bool] = mapped_column(Boolean, default=False)

    slippage_buy_pct: Mapped[float] = mapped_column(Float, default=0.0)
    slippage_sell_pct: Mapped[float] = mapped_column(Float, default=0.0)
    fees_usd: Mapped[float] = mapped_column(Float, default=0.0)
    pnl_usd: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    peak_gain_pct: Mapped[float] = mapped_column(Float, default=0.0)
    hold_seconds: Mapped[int] = mapped_column(Integer, default=0)
    equity_after: Mapped[float] = mapped_column(Float, default=0.0)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class EquityPoint(Base):
    __tablename__ = "equity_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    equity: Mapped[float] = mapped_column(Float, default=0.0)
    cash: Mapped[float] = mapped_column(Float, default=0.0)
    open_value: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LogEntry(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    level: Mapped[str] = mapped_column(String(16), default="info", index=True)
    category: Mapped[str] = mapped_column(String(32), default="system")
    message: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SkippedToken(Base):
    __tablename__ = "skipped_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mint: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    symbol: Mapped[str] = mapped_column(String(32), default="")
    decision_time: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Decision-time features
    score: Mapped[float] = mapped_column(Float, default=0.0)
    safety_score: Mapped[float] = mapped_column(Float, default=0.0)
    opportunity_score: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity_usd: Mapped[float] = mapped_column(Float, default=0.0)
    market_cap_usd: Mapped[float] = mapped_column(Float, default=0.0)
    num_holders: Mapped[int] = mapped_column(Integer, default=0)
    num_buyers: Mapped[int] = mapped_column(Integer, default=0)
    verdict: Mapped[str] = mapped_column(String(16), default="AVOID")
    reject_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Decision metadata
    hard_rejected: Mapped[bool] = mapped_column(Boolean, default=False)
    red_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    green_flags: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Future price/liquidity tracking (DexScreener)
    price_5m: Mapped[float] = mapped_column(Float, default=0.0)
    price_15m: Mapped[float] = mapped_column(Float, default=0.0)
    price_1h: Mapped[float] = mapped_column(Float, default=0.0)
    price_4h: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity_5m: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity_15m: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity_1h: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity_4h: Mapped[float] = mapped_column(Float, default=0.0)
    is_real_runner: Mapped[bool] = mapped_column(Boolean, default=False)


class TokenSnapshot(Base):
    """Periodic price path used for backtests and missed-opportunity analysis."""

    __tablename__ = "token_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mint: Mapped[str] = mapped_column(String(64), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    price_usd: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity_usd: Mapped[float] = mapped_column(Float, default=0.0)
    market_cap_usd: Mapped[float] = mapped_column(Float, default=0.0)

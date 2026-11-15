from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import get_runtime
from app.config import PRESETS
from app.db.models import EquityPoint, LogEntry, Token, Trade
from app.db.session import SessionLocal
from app.serializers import log_dict, token_dict, trade_dict
from app.utils import iso, utcnow

router = APIRouter(prefix="/api")


class BotBody(BaseModel):
    enabled: bool


class BacktestBody(BaseModel):
    overrides: dict[str, Any] = Field(default_factory=dict)


class SpawnBody(BaseModel):
    count: int = 1


class SeedBody(BaseModel):
    force: bool = False


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    runtime = get_runtime(request)
    return {
        "status": "ok",
        "mode": runtime.mode,
        "scanner": runtime.listener.health(),
        "bot_enabled": runtime.bot_enabled,
        "uptime_seconds": runtime.snapshot()["health"]["uptime_seconds"],
    }


@router.get("/state")
async def state(request: Request) -> dict[str, Any]:
    return get_runtime(request).snapshot()


@router.get("/tokens")
async def list_tokens(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    offset: int = 0,
    verdict: str | None = None,
    q: str | None = None,
    hard_rejected: bool | None = None,
    rugged: bool | None = None,
) -> dict[str, Any]:
    runtime = get_runtime(request)
    async with SessionLocal() as session:
        stmt = select(Token).order_by(Token.created_at.desc())
        if verdict:
            stmt = stmt.where(Token.verdict == verdict.upper())
        if hard_rejected is not None:
            stmt = stmt.where(Token.hard_rejected.is_(hard_rejected))
        if rugged is not None:
            stmt = stmt.where(Token.rugged.is_(rugged))
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(
                Token.name.ilike(like) | Token.symbol.ilike(like) | Token.mint.ilike(like)
            )
        rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    return {"items": [token_dict(token) for token in rows], "count": len(rows), "limit": limit, "offset": offset}


@router.get("/tokens/{mint}")
async def token_detail(request: Request, mint: str) -> dict[str, Any]:
    runtime = get_runtime(request)
    async with SessionLocal() as session:
        token = (await session.execute(select(Token).where(Token.mint == mint))).scalar_one_or_none()
        if not token:
            raise HTTPException(status_code=404, detail="Token not found")
        trades = (
            await session.execute(select(Trade).where(Trade.token_mint == mint).order_by(Trade.opened_at.desc()))
        ).scalars().all()
    data = token_dict(token, include_checks=True)
    live = runtime.feed.tokens.get(mint)
    if live:
        data["price_usd"] = live["price"]
        data["liquidity_usd"] = live["liquidity"]
        data["market_cap_usd"] = live["market_cap"]
        data["peak_price_usd"] = live["peak_price"]
        data["rugged"] = live["rugged"]
        data["initial_price_usd"] = token.initial_price_usd or live["initial_price"]
        data["price_history"] = live["history"]
        data["peak_gain_pct"] = (
            round((live["peak_price"] / live["initial_price"] - 1) * 100, 2) if live["initial_price"] > 0 else 0.0
        )
    data["trades"] = [trade_dict(trade) for trade in trades]
    data["links"] = {
        "solscan": f"https://solscan.io/token/{mint}",
        "dexscreener": f"https://dexscreener.com/solana/{mint}",
        "rugcheck": f"https://rugcheck.xyz/tokens/{mint}",
        "pumpfun": f"https://pump.fun/coin/{mint}",
    }
    return data


@router.get("/positions")
async def positions(request: Request) -> dict[str, Any]:
    runtime = get_runtime(request)
    return {"items": runtime.engine.positions_view(), "wallet": runtime.engine.wallet()}


@router.get("/trades")
async def list_trades(
    request: Request,
    status: str | None = "closed",
    result: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    mint: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = 0,
) -> dict[str, Any]:
    async with SessionLocal() as session:
        stmt = select(Trade).order_by(Trade.opened_at.desc())
        if status and status != "all":
            stmt = stmt.where(Trade.status == status)
        if mint:
            stmt = stmt.where(Trade.token_mint == mint)
        if min_score is not None:
            stmt = stmt.where(Trade.score_at_entry >= min_score)
        if max_score is not None:
            stmt = stmt.where(Trade.score_at_entry <= max_score)
        rows = (await session.execute(stmt)).scalars().all()
    if result == "win":
        rows = [trade for trade in rows if trade.status == "closed" and trade.pnl_usd > 0]
    elif result == "loss":
        rows = [trade for trade in rows if trade.status == "closed" and trade.pnl_usd <= 0]
    elif result == "rug":
        rows = [trade for trade in rows if any("rugged" in str(reason).lower() for reason in (trade.exit_reasons or []))]
    total = len(rows)
    selected = rows[offset : offset + limit]
    return {"items": [trade_dict(trade) for trade in selected], "total": total, "limit": limit, "offset": offset}


@router.get("/trades/export.csv")
async def export_trades(request: Request) -> Response:
    async with SessionLocal() as session:
        rows = (await session.execute(select(Trade).order_by(Trade.opened_at.desc()))).scalars().all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "opened_at",
            "closed_at",
            "mint",
            "symbol",
            "name",
            "status",
            "score",
            "safety",
            "opportunity",
            "size_usd",
            "entry_price",
            "exit_price",
            "pnl_usd",
            "pnl_pct",
            "fees_usd",
            "slippage_buy_pct",
            "slippage_sell_pct",
            "hold_seconds",
            "exit_reasons",
        ]
    )
    for trade in rows:
        writer.writerow(
            [
                trade.id,
                iso(trade.opened_at),
                iso(trade.closed_at),
                trade.token_mint,
                trade.symbol,
                trade.token_name,
                trade.status,
                trade.score_at_entry,
                trade.safety_at_entry,
                trade.opportunity_at_entry,
                trade.size_usd,
                trade.entry_price,
                trade.exit_price,
                trade.pnl_usd,
                trade.pnl_pct,
                trade.fees_usd,
                trade.slippage_buy_pct,
                trade.slippage_sell_pct,
                trade.hold_seconds,
                " | ".join(trade.exit_reasons or []),
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="memeradar-trades.csv"'},
    )


@router.get("/equity")
async def equity(request: Request, range: str = Query("24H", alias="range")) -> dict[str, Any]:
    runtime = get_runtime(request)
    now = utcnow()
    delta_map = {"1H": timedelta(hours=1), "24H": timedelta(hours=24), "7D": timedelta(days=7), "ALL": None}
    delta = delta_map.get(range.upper(), timedelta(hours=24))
    async with SessionLocal() as session:
        stmt = select(EquityPoint).order_by(EquityPoint.ts.asc())
        if delta:
            stmt = stmt.where(EquityPoint.ts >= now - delta)
        points = (await session.execute(stmt.limit(4000))).scalars().all()
    wallet = runtime.engine.wallet()
    series = [{"t": iso(point.ts), "equity": point.equity, "cash": point.cash} for point in points]
    series.append({"t": iso(now), "equity": wallet["equity"], "cash": wallet["cash"]})
    return {"range": range.upper(), "points": series, "wallet": wallet, "starting_balance": runtime.engine.starting_balance}


@router.get("/metrics")
async def metrics(request: Request) -> dict[str, Any]:
    runtime = get_runtime(request)
    return {"metrics": runtime.metrics_cache, "wallet": runtime.engine.wallet(), "breaker": runtime.engine.breaker()}


@router.get("/analytics")
async def analytics(request: Request) -> dict[str, Any]:
    return await get_runtime(request).analytics()


@router.get("/logs")
async def logs(
    request: Request,
    level: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = 0,
) -> dict[str, Any]:
    async with SessionLocal() as session:
        stmt = select(LogEntry).order_by(LogEntry.ts.desc())
        if level and level != "all":
            stmt = stmt.where(LogEntry.level == level)
        rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    return {"items": [log_dict(entry) for entry in reversed(rows)], "count": len(rows)}


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    runtime = get_runtime(request)
    return {"config": runtime.config.model_dump(), "runtime": {"mode": runtime.mode, "bot_enabled": runtime.bot_enabled}}


@router.put("/config")
async def put_config(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    runtime = get_runtime(request)
    try:
        config = await runtime.save_config(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {exc}") from exc
    return {"config": config.model_dump(), "runtime": {"mode": runtime.mode, "bot_enabled": runtime.bot_enabled}}


@router.post("/config/reset")
async def reset_config(request: Request) -> dict[str, Any]:
    runtime = get_runtime(request)
    config = await runtime.reset_config()
    return {"config": config.model_dump()}


@router.get("/config/presets")
async def presets() -> dict[str, Any]:
    descriptions = {
        "conservative": "High score threshold, tight stop, small size, 8% daily breaker.",
        "balanced": "Default MemeRadar profile — 74+ score, 25% stop, 10% max position.",
        "degen": "Lower thresholds, bigger positions, wider stops, 25% daily breaker.",
    }
    return {"presets": [{"name": name, "description": descriptions.get(name, "")} for name in PRESETS]}


@router.post("/config/preset/{name}")
async def apply_preset(request: Request, name: str) -> dict[str, Any]:
    runtime = get_runtime(request)
    try:
        config = await runtime.apply_preset(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"config": config.model_dump()}


@router.post("/bot")
async def set_bot(request: Request, body: BotBody) -> dict[str, Any]:
    return await get_runtime(request).set_bot(body.enabled)


@router.post("/positions/{trade_id}/close")
async def close_position(request: Request, trade_id: int) -> dict[str, Any]:
    result = await get_runtime(request).close_position(trade_id)
    if not result:
        raise HTTPException(status_code=404, detail="Position not found")
    return {"trade": result}


@router.post("/account/reset")
async def reset_account(request: Request) -> dict[str, Any]:
    return await get_runtime(request).reset_account()


@router.post("/backtest")
async def backtest(request: Request, body: BacktestBody | None = None) -> dict[str, Any]:
    runtime = get_runtime(request)
    overrides = body.overrides if body else {}
    return await runtime.run_backtest(overrides)


@router.get("/missed")
async def missed(request: Request, kind: str = "missed") -> dict[str, Any]:
    runtime = get_runtime(request)
    data = await runtime.analytics()
    if kind == "dodged":
        return {"items": data["bullets_dodged"], "counts": data["counts"]}
    return {"items": data["missed_opportunities"], "counts": data["counts"]}


@router.post("/demo/spawn")
async def spawn(request: Request, body: SpawnBody) -> dict[str, Any]:
    runtime = get_runtime(request)
    if runtime.mode != "demo":
        raise HTTPException(status_code=400, detail="Demo spawn is only available in demo mode")
    count = await runtime.spawn_demo(body.count)
    return {"spawned": count}


@router.post("/demo/seed")
async def seed(request: Request, body: SeedBody) -> dict[str, Any]:
    runtime = get_runtime(request)
    if runtime.mode != "demo":
        raise HTTPException(status_code=400, detail="Seeding is only available in demo mode")
    result = await runtime.seed_more(force=body.force)
    return result


@router.get("/sol")
async def sol(request: Request) -> dict[str, Any]:
    runtime = get_runtime(request)
    return {"price": runtime.feed.sol_price_now()}

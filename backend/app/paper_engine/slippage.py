from __future__ import annotations

from typing import TYPE_CHECKING

from app.utils import clamp

if TYPE_CHECKING:
    from app.config import PaperSection


def amm_slippage(size_usd: float, liquidity_usd: float) -> float:
    """Constant-product price impact for a trade against a pool of given depth."""
    if size_usd <= 0:
        return 0.0
    if liquidity_usd <= 0:
        return 0.99
    quote_reserve = max(liquidity_usd / 2.0, 1.0)
    x = min(size_usd / quote_reserve, 0.95)
    impact = (1.0 + x) ** 2 - 1.0
    return clamp(impact, 0.0, 0.95)


def random_slippage(rng, paper: "PaperSection") -> float:
    low = max(0.0, paper.random_slippage_min_pct)
    high = max(low, paper.random_slippage_max_pct)
    return rng.uniform(low, high)


def execution_slippage(size_usd: float, liquidity_usd: float, rng, paper: "PaperSection") -> float:
    return clamp(amm_slippage(size_usd, liquidity_usd) + random_slippage(rng, paper), 0.0, 0.99)


def execution_price(market_price: float, slippage: float, side: str) -> float:
    if side == "buy":
        return market_price * (1.0 + slippage)
    return market_price * max(0.01, 1.0 - slippage)


def fee_usd(notional: float, paper: "PaperSection", sol_price: float) -> float:
    network = (paper.priority_fee_sol + paper.jito_tip_sol) * max(sol_price, 0.0)
    return max(0.0, notional * paper.taker_fee_pct + network)

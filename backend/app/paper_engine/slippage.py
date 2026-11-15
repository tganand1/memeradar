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
    """AMM slippage + random slippage, capped at 99%."""
    return clamp(amm_slippage(size_usd, liquidity_usd) + random_slippage(rng, paper), 0.0, 0.99)


def execution_price(market_price: float, slippage: float, side: str) -> float:
    if side == "buy":
        return market_price * (1.0 + slippage)
    return market_price * max(0.01, 1.0 - slippage)


def fee_usd(notional: float, paper: "PaperSection", sol_price: float) -> float:
    network = (paper.priority_fee_sol + paper.jito_tip_sol) * max(sol_price, 0.0)
    return max(0.0, notional * paper.taker_fee_pct + network)


def jupiter_quote(mint: str, amount_raw: int, sol_price: float, paper: "PaperSection") -> dict | None:
    """Fetch a Jupiter quote for a given input amount.
    
    Returns the quote dict or None on failure. This simulates the price the bot
    could actually obtain at the moment — no look-ahead.
    """
    import httpx
    from app.clients import JUPITER_QUOTE_URL
    
    try:
        async def _fetch():
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    JUPITER_QUOTE_URL,
                    params={
                        "inputMint": mint,
                        "outputMint": "So11111111111111111111111111111111111111112",
                        "amount": amount_raw,
                        "slippageBps": 1500,
                        "restrictIntermediateTokens": "true",
                    },
                )
                if resp.status_code >= 400:
                    return None
                return resp.json()
        
        return asyncio.run(_fetch())
    except Exception as e:
        import logging
        logging.getLogger("memeradar").warning(f"Jupiter quote failed: {e}")
        return None


def entry_price(market_price: float, size_usd: float, liquidity_usd: float, rng, paper: "PaperSection") -> float:
    """Compute the effective entry price including AMM slippage, random slippage,
    priority fee, JITO tip, and 1-3s latency drift.
    """
    # AMM price impact
    slippage = amm_slippage(size_usd, liquidity_usd)
    # Random variance (simulates 1-3s latency / market movement)
    slippage = clamp(slippage + random_slippage(rng, paper), 0.0, 1.0)
    # Priority fee + JITO tip equivalent in price impact
    # Rough: (priority_fee_sol + jito_tip_sol) / notional_in_sol
    network_impact = (paper.priority_fee_sol + paper.jito_tip_sol) / max(size_usd / market_price, 1.0)
    total_slippage = clamp(slippage + network_impact, 0.0, 1.0)
    return execution_price(market_price, total_slippage, "buy")


def exit_price(market_price: float, size_usd: float, liquidity_usd: float, rng, paper: "PaperSection") -> float:
    """Compute the effective exit price including AMM slippage, random slippage,
    priority fee, JITO tip, and 1-3s latency drift.
    Selling into thin liquidity costs more (higher impact).
    """
    # AMM price impact (selling)
    slippage = amm_slippage(size_usd, liquidity_usd)
    # Random variance
    slippage = clamp(slippage + random_slippage(rng, paper), 0.0, 1.0)
    # Network fees equivalent
    network_impact = (paper.priority_fee_sol + paper.jito_tip_sol) / max(size_usd / market_price, 1.0)
    total_slippage = clamp(slippage + network_impact, 0.0, 1.0)
    return execution_price(market_price, total_slippage, "sell")

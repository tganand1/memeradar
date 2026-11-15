from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from app.analyzer.types import NewToken
from app.utils import utcnow

if TYPE_CHECKING:
    from app.listener.manager import ListenerManager


def token_from_pair(pair: dict[str, Any], source: str = "dexscreener") -> NewToken | None:
    base = pair.get("baseToken") or {}
    mint = base.get("address")
    if not mint:
        return None
    info = pair.get("info") or {}
    socials = info.get("socials") or []
    twitter = next((item.get("url") for item in socials if item.get("type") == "twitter"), None)
    telegram = next((item.get("url") for item in socials if item.get("type") == "telegram"), None)
    websites = info.get("websites") or []
    return NewToken(
        mint=mint,
        symbol=base.get("symbol") or mint[:4],
        name=base.get("name") or "Unknown Token",
        creator=None,
        source=source,
        created_at=utcnow(),
        liquidity_usd=float((pair.get("liquidity") or {}).get("usd") or 0.0),
        market_cap_usd=float(pair.get("marketCap") or pair.get("fdv") or 0.0),
        price_usd=float(pair.get("priceUsd") or 0.0),
        image_url=info.get("imageUrl"),
        website=websites[0].get("url") if websites else None,
        twitter=twitter,
        telegram=telegram,
        is_demo=False,
    )


class DexScreenerPoller:
    """Fallback listener that polls latest token profiles and boosts."""

    def __init__(self, manager: "ListenerManager") -> None:
        self.manager = manager

    async def run(self) -> None:
        manager = self.manager
        while manager._running:
            try:
                profiles, boosts = await asyncio.gather(
                    manager.clients.dexscreener_latest_profiles(),
                    manager.clients.dexscreener_latest_boosts(),
                    return_exceptions=True,
                )
                if isinstance(profiles, Exception):
                    profiles = []
                if isinstance(boosts, Exception):
                    boosts = []
                mints: list[str] = []
                seen: set[str] = set()
                for item in [*profiles, *boosts]:
                    mint = item.get("tokenAddress")
                    if mint and mint not in seen:
                        seen.add(mint)
                        mints.append(mint)
                new_mints = [mint for mint in mints if mint not in manager._seen][:40]
                if new_mints:
                    pairs = await manager.clients.dexscreener_token_batch(new_mints)
                    added = 0
                    for mint in new_mints:
                        pair = pairs.get(mint)
                        if not pair:
                            continue
                        token = token_from_pair(pair, source="dexscreener")
                        if token and await manager.emit(token):
                            added += 1
                    manager.set_source("dexscreener", "polling", f"{added} new token(s)")
                else:
                    manager.set_source("dexscreener", "polling", "no new profiles")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                manager.set_source("dexscreener", "error", str(exc)[:120])
                await manager.log_cb("warning", "listener", f"DexScreener poll failed: {exc}")
            interval = max(3.0, manager.get_config().listener.dexscreener_poll_seconds)
            await asyncio.sleep(interval)

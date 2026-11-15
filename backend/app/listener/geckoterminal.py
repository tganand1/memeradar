from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from app.analyzer.types import NewToken
from app.utils import safe_float, utcnow

if TYPE_CHECKING:
    from app.listener.manager import ListenerManager


def _mint_from_resource_id(resource_id: str | None) -> str | None:
    if not resource_id or "_" not in resource_id:
        return None
    network, _, mint = resource_id.partition("_")
    if network != "solana" or not mint:
        return None
    return mint


def tokens_from_payload(payload: dict[str, Any] | None) -> list[NewToken]:
    """Map GeckoTerminal new-pool payloads into NewToken records."""
    included: dict[str, dict[str, Any]] = {}
    for item in (payload or {}).get("included") or []:
        if isinstance(item, dict) and item.get("id"):
            included[str(item["id"])] = item

    tokens: list[NewToken] = []
    for pool in (payload or {}).get("data") or []:
        if not isinstance(pool, dict):
            continue
        relationships = pool.get("relationships") or {}
        base_ref = ((relationships.get("base_token") or {}).get("data") or {})
        mint = _mint_from_resource_id(base_ref.get("id"))
        if not mint:
            continue
        attrs = pool.get("attributes") or {}
        meta = (included.get(str(base_ref.get("id"))) or {}).get("attributes") or {}
        symbol = str(meta.get("symbol") or "").strip()
        name = str(meta.get("name") or "").strip()
        if not symbol:
            pool_name = str(attrs.get("name") or "")
            symbol = pool_name.split("/")[0].strip() or mint[:4].upper()
        if not name:
            name = symbol
        liquidity = safe_float(attrs.get("reserve_in_usd"))
        market_cap = safe_float(attrs.get("fdv_usd"), safe_float(attrs.get("market_cap_usd")))
        price = safe_float(attrs.get("base_token_price_usd"))
        if price <= 0:
            continue
        tokens.append(
            NewToken(
                mint=mint,
                symbol=symbol[:32],
                name=name[:128],
                creator=None,
                source="geckoterminal",
                created_at=utcnow(),
                liquidity_usd=liquidity,
                market_cap_usd=market_cap,
                price_usd=price,
                image_url=meta.get("image_url"),
                is_demo=False,
            )
        )
    return tokens


class GeckoTerminalPoller:
    """Keyless fallback discovery for new Solana pools."""

    def __init__(self, manager: "ListenerManager") -> None:
        self.manager = manager

    async def run(self) -> None:
        manager = self.manager
        while manager._running:
            try:
                payload = await manager.clients.geckoterminal_new_pools()
                added = 0
                for token in tokens_from_payload(payload):
                    if token.mint in manager._seen:
                        continue
                    if await manager.emit(token):
                        added += 1
                manager.set_source("geckoterminal", "polling", f"{added} new pool(s)")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                manager.set_source("geckoterminal", "error", str(exc)[:120])
                await manager.log_cb("warning", "listener", f"GeckoTerminal poll failed: {exc}")
            interval = max(15.0, manager.get_config().listener.geckoterminal_poll_seconds)
            await asyncio.sleep(interval)

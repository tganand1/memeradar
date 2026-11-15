from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.env import ENV
from app.utils import TokenBucket, safe_float

log = logging.getLogger("memeradar.clients")

SOL_MINT = "So11111111111111111111111111111111111111112"
JUPITER_QUOTE_URL = "https://lite-api.jup.ag/swap/v1/quote"


class MarketClients:
    """Thin async clients for every market data source, all failure-tolerant."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self.bucket = TokenBucket(6.0, burst=6)
        self.env = ENV

    async def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(8.0, connect=5.0),
                headers={"User-Agent": "MemeRadar/1.0 (paper trading)"},
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _get_json(self, url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
        await self.bucket.acquire()
        try:
            client = await self.client()
            response = await client.get(url, params=params, headers=headers)
            if response.status_code >= 400:
                log.warning("GET %s -> %s", url, response.status_code)
                return None
            return response.json()
        except Exception as exc:
            log.warning("GET %s failed: %s", url, exc)
            return None

    async def _post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> Any:
        await self.bucket.acquire()
        try:
            client = await self.client()
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code >= 400:
                log.warning("POST %s -> %s", url, response.status_code)
                return None
            return response.json()
        except Exception as exc:
            log.warning("POST %s failed: %s", url, exc)
            return None

    # ── DexScreener (no key) ───────────────────────────────────────
    async def dexscreener_token(self, mint: str) -> dict[str, Any] | None:
        data = await self._get_json(f"https://api.dexscreener.com/latest/dex/tokens/{mint}")
        pairs = (data or {}).get("pairs") or []
        solana = [pair for pair in pairs if pair.get("chainId") == "solana"]
        if not solana:
            return None
        return max(solana, key=lambda pair: safe_float((pair.get("liquidity") or {}).get("usd")))

    async def dexscreener_token_batch(self, mints: list[str]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for start in range(0, len(mints), 25):
            chunk = mints[start : start + 25]
            data = await self._get_json("https://api.dexscreener.com/latest/dex/tokens/" + ",".join(chunk))
            for pair in (data or {}).get("pairs") or []:
                if pair.get("chainId") != "solana":
                    continue
                base = (pair.get("baseToken") or {}).get("address")
                if not base:
                    continue
                current = out.get(base)
                if current is None or safe_float((pair.get("liquidity") or {}).get("usd")) > safe_float(
                    (current.get("liquidity") or {}).get("usd")
                ):
                    out[base] = pair
        return out

    async def dexscreener_latest_profiles(self) -> list[dict[str, Any]]:
        data = await self._get_json("https://api.dexscreener.com/token-profiles/latest/v1")
        return [item for item in (data or []) if isinstance(item, dict) and item.get("chainId") == "solana"]

    async def dexscreener_latest_boosts(self) -> list[dict[str, Any]]:
        data = await self._get_json("https://api.dexscreener.com/token-boosts/latest/v1")
        return [item for item in (data or []) if isinstance(item, dict) and item.get("chainId") == "solana"]

    # ── GeckoTerminal (no key) ────────────────────────────────────
    async def geckoterminal_new_pools(self, page: int = 1) -> dict[str, Any] | None:
        return await self._get_json(
            "https://api.geckoterminal.com/api/v2/networks/solana/new_pools",
            params={"page": page},
            headers={"Accept": "application/json"},
        )

    async def geckoterminal_token(self, mint: str) -> dict[str, Any] | None:
        data = await self._get_json(
            f"https://api.geckoterminal.com/api/v2/networks/solana/tokens/{mint}",
            headers={"Accept": "application/json"},
        )
        return (data or {}).get("data")

    # ── RugCheck (public, key optional) ───────────────────────────
    async def rugcheck_summary(self, mint: str) -> dict[str, Any] | None:
        headers = {"X-API-KEY": self.env.rugcheck_api_key} if self.env.rugcheck_api_key else None
        return await self._get_json(f"https://api.rugcheck.xyz/v1/tokens/{mint}/report/summary", headers=headers)

    async def rugcheck_report(self, mint: str) -> dict[str, Any] | None:
        headers = {"X-API-KEY": self.env.rugcheck_api_key} if self.env.rugcheck_api_key else None
        return await self._get_json(f"https://api.rugcheck.xyz/v1/tokens/{mint}/report", headers=headers)

    # ── Helius RPC (optional key) ─────────────────────────────────
    async def helius_rpc(self, method: str, params: list[Any]) -> Any:
        if not self.env.helius_rpc_url:
            return None
        data = await self._post_json(
            self.env.helius_rpc_url,
            {"jsonrpc": "2.0", "id": "memeradar", "method": method, "params": params},
        )
        if not data:
            return None
        if data.get("error"):
            log.warning("Helius %s error: %s", method, data.get("error"))
            return None
        return data.get("result")

    async def mint_info(self, mint: str) -> dict[str, Any] | None:
        result = await self.helius_rpc("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
        try:
            return result["value"]["data"]["parsed"]["info"]
        except (KeyError, TypeError):
            return None

    async def creator_assets(self, creator: str) -> list[dict[str, Any]]:
        result = await self.helius_rpc(
            "getAssetsByCreator",
            {"creatorAddress": creator, "onlyVerified": False, "page": 1, "limit": 50},
        )
        try:
            return result.get("items") or []
        except AttributeError:
            return []

    async def jupiter_sell_quote(self, mint: str, amount_raw: int = 1_000_000) -> bool | None:
        """Quote-only sell check. Never signs or sends a transaction."""
        data = await self._get_json(
            JUPITER_QUOTE_URL,
            params={
                "inputMint": mint,
                "outputMint": SOL_MINT,
                "amount": amount_raw,
                "slippageBps": 1500,
                "restrictIntermediateTokens": "true",
            },
        )
        if data is None:
            return None
        try:
            return int(data.get("outAmount", 0)) > 0
        except (TypeError, ValueError):
            return False

    async def sol_price(self) -> float | None:
        pair = await self.dexscreener_token(SOL_MINT)
        if not pair:
            return None
        price = safe_float(pair.get("priceUsd"))
        return price if price > 0 else None


async def gather_with_timeout(coros: list[Any], timeout: float = 10.0) -> list[Any]:
    results = await asyncio.gather(*coros, return_exceptions=True)
    out: list[Any] = []
    for item in results:
        out.append(None if isinstance(item, Exception) else item)
    return out

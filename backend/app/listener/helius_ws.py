from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from typing import TYPE_CHECKING, Any

import websockets

from app.analyzer.types import NewToken
from app.utils import utcnow

if TYPE_CHECKING:
    from app.listener.manager import ListenerManager

log = logging.getLogger("memeradar.helius")

PROGRAMS = {
    "pump.fun": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
    "pumpswap": "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",
    "raydium-amm": "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
    "raydium-cpmm": "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C",
}
MINT_RE = re.compile(r"mint:\s*([1-9A-HJ-NP-Za-km-z]{32,44})")
CREATE_HINTS = ("Instruction: Create", "Instruction: InitializeMint", "Instruction: Initialize", "initialize2")


class HeliusWebSocket:
    """Auto-reconnecting logsSubscribe listener for new pools and token creations."""

    def __init__(self, manager: "ListenerManager") -> None:
        self.manager = manager
        self.semaphore = asyncio.Semaphore(4)

    async def run(self) -> None:
        manager = self.manager
        attempt = 0
        while manager._running:
            url = manager.clients.env.helius_ws_url
            if not url:
                return
            try:
                manager.set_source("helius", "connecting")
                async with websockets.connect(url, ping_interval=20, ping_timeout=20, max_size=2**22, open_timeout=15) as ws:
                    manager.set_source("helius", "connected", "subscribed to pump.fun / Raydium / PumpSwap")
                    for index, (name, program) in enumerate(PROGRAMS.items(), start=1):
                        await ws.send(
                            json.dumps(
                                {
                                    "jsonrpc": "2.0",
                                    "id": index,
                                    "method": "logsSubscribe",
                                    "params": [{"mentions": [program]}, {"commitment": "confirmed"}],
                                }
                            )
                        )
                    attempt = 0
                    while manager._running:
                        raw = await asyncio.wait_for(ws.recv(), timeout=45)
                        try:
                            await self._handle(raw)
                        except Exception:
                            log.exception("Failed to handle Helius message")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                attempt += 1
                manager.reconnects += 1
                delay = min(30.0, (2 ** min(attempt, 5)) + random.uniform(0, 2))
                manager.set_source("helius", "reconnecting", f"{type(exc).__name__}: {str(exc)[:100]}")
                await manager.log_cb("warning", "listener", f"Helius WS disconnected, reconnecting in {delay:.1f}s")
                await asyncio.sleep(delay)

    async def _handle(self, raw: str | bytes) -> None:
        try:
            message = json.loads(raw)
        except Exception:
            return
        if message.get("method") != "logsNotification":
            return
        value = (((message.get("params") or {}).get("result") or {}).get("value") or {})
        logs = value.get("logs") or []
        if not logs:
            return
        text = "\n".join(str(line) for line in logs)
        if not any(hint in text for hint in CREATE_HINTS) and "mint:" not in text:
            return
        mints = MINT_RE.findall(text)
        for mint in dict.fromkeys(mints):
            if mint in self.manager._seen:
                continue
            asyncio.create_task(self._process(mint))

    async def _process(self, mint: str) -> None:
        async with self.semaphore:
            try:
                token = await self.manager.enrich_from_dexscreener(mint, source="helius")
                if token is None:
                    token = NewToken(
                        mint=mint,
                        symbol=mint[:4].upper(),
                        name="New Solana token",
                        creator=None,
                        source="helius",
                        created_at=utcnow(),
                        liquidity_usd=0.0,
                        market_cap_usd=0.0,
                        price_usd=0.0,
                        is_demo=False,
                    )
                await self.manager.emit(token)
            except Exception as exc:
                await self.manager.log_cb("warning", "listener", f"Helius token enrichment failed: {exc}")

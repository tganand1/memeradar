from __future__ import annotations

import asyncio
import sys
from app.analyzer.clients import MarketClients
from app.env import ENV

async def main() -> None:
    print("Checking MemeRadar API keys and market feed connectivity...")
    clients = MarketClients()
    
    # 1. DexScreener (public)
    try:
        ds = await clients.dexscreener_token("So11111111111111111111111111111111111111112")
        print(" [OK] DexScreener API: Reachable")
    except Exception as exc:
        print(f" [FAIL] DexScreener API: {exc}")

    # 2. GeckoTerminal (public)
    try:
        gt = await clients.geckoterminal_new_pools()
        print(" [OK] GeckoTerminal API: Reachable")
    except Exception as exc:
        print(f" [FAIL] GeckoTerminal API: {exc}")

    # 3. RugCheck (public/key)
    try:
        rc = await clients.rugcheck_summary("So11111111111111111111111111111111111111112")
        print(" [OK] RugCheck API: Reachable")
    except Exception as exc:
        print(f" [FAIL] RugCheck API: {exc}")

    # 4. Helius RPC (key optional)
    if ENV.helius_api_key:
        try:
            hp = await clients.helius_rpc("getHealth", [])
            print(" [OK] Helius RPC: Reachable (API key configured)")
        except Exception as exc:
            print(f" [FAIL] Helius RPC: {exc}")
    else:
        print(" [INFO] Helius RPC: API key not provided (using polling fallbacks)")

    await clients.close()
    print("Key check complete.")

if __name__ == "__main__":
    asyncio.run(main())

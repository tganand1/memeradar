from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"


def database_file(mode: str) -> Path:
    name = "memeradar_demo.db" if mode == "demo" else "memeradar_live.db"
    return DATA_DIR / name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MemeRadar — Solana meme coin paper trading bot")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--demo", action="store_true", help="force demo mode (fake tokens, no API keys)")
    group.add_argument("--live", action="store_true", help="force live mode (uses API keys when available)")
    parser.add_argument("--seed", action="store_true", help="seed demo data (80 tokens, historical trades)")
    parser.add_argument("--reset", action="store_true", help="delete the local SQLite database before starting")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument("--reload", action="store_true", help="uvicorn auto-reload (development)")
    return parser.parse_args()


def prepare_database(mode: str, seed: bool, reset: bool) -> None:
    db_file = database_file(mode)
    if reset and db_file.exists():
        for suffix in ("", "-wal", "-shm"):
            target = Path(str(db_file) + suffix)
            if target.exists():
                target.unlink()
        print(f"[MemeRadar] Deleted {db_file}")

    if seed:
        from app.config import build_config
        from app.db.session import init_db
        from app.demo.seed import seed_demo_data

        async def run() -> None:
            await init_db()
            result = await seed_demo_data(build_config(), force=True)
            print(f"[MemeRadar] Seed result: {result}")

        asyncio.run(run())


def main() -> None:
    args = parse_args()
    mode = "demo" if args.demo else "live"
    if args.seed and mode != "demo":
        print("[MemeRadar] --seed is only available with --demo (live data must stay real).")
        sys.exit(2)
    os.environ["MEMERADAR_MODE"] = mode

    prepare_database(mode, args.seed, args.reset)
    print(f"[MemeRadar] Mode: {mode.upper()} — database: {database_file(mode)}")

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()

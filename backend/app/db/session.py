from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.env import ENV

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MODE = ENV.mode if ENV.mode in ("demo", "live") else "live"
DB_FILE = DATA_DIR / ("memeradar_demo.db" if MODE == "demo" else "memeradar_live.db")

DEFAULT_URL = f"sqlite+aiosqlite:///{DB_FILE.as_posix()}"
DATABASE_URL = ENV.database_url or DEFAULT_URL

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"timeout": 30} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    if DATABASE_URL.startswith("sqlite"):
        from sqlalchemy import text

        async with engine.begin() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))

            # ── Migration: ensure new columns exist on Token table ────────────
            # Check existing columns via PRAGMA
            result = await conn.execute(text("PRAGMA table_info(tokens)"))
            existing_cols = {row[1] for row in result.fetchall()}

            # New columns on Token (name, type, default, nullable)
            new_token_cols = [
                ("skipped", "BOOLEAN", "0", True),        # default False
                ("reject_reason", "VARCHAR(128)", None, True),  # nullable
                ("skipped_at", "DATETIME", None, True),   # nullable
                ("price_5m", "FLOAT", "0.0", True),
                ("price_15m", "FLOAT", "0.0", True),
                ("price_1h", "FLOAT", "0.0", True),
                ("price_4h", "FLOAT", "0.0", True),
                ("liquidity_5m", "FLOAT", "0.0", True),
                ("liquidity_15m", "FLOAT", "0.0", True),
                ("liquidity_1h", "FLOAT", "0.0", True),
                ("liquidity_4h", "FLOAT", "0.0", True),
                ("is_real_runner", "BOOLEAN", "0", True),
            ]

            for col_name, col_type, default_val, is_nullable in new_token_cols:
                if col_name not in existing_cols:
                    null_str = "" if not is_nullable else " NULL"
                    default_str = f" DEFAULT {default_val}" if default_val is not None else ""
                    await conn.execute(
                        text(f'ALTER TABLE tokens ADD COLUMN "{col_name}" {col_type}{default_str}{null_str}')
                    )

            # ── Create SkippedToken table if missing ────────────────────────
            result2 = await conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='skipped_tokens'"
                )
            )
            if not result2.scalar():
                await conn.execute(
                    text(
                        """CREATE TABLE skipped_tokens (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           mint TEXT NOT NULL,
                           name TEXT DEFAULT '',
                           symbol TEXT DEFAULT '',
                           decision_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                           score FLOAT DEFAULT 0.0,
                           safety_score FLOAT DEFAULT 0.0,
                           opportunity_score FLOAT DEFAULT 0.0,
                           liquidity_usd FLOAT DEFAULT 0.0,
                           market_cap_usd FLOAT DEFAULT 0.0,
                           num_holders INTEGER DEFAULT 0,
                           num_buyers INTEGER DEFAULT 0,
                           verdict TEXT DEFAULT 'AVOID',
                           reject_reason TEXT,
                           hard_rejected BOOLEAN DEFAULT FALSE,
                           red_flags JSON DEFAULT '[]',
                           green_flags JSON DEFAULT '[]',
                           price_5m FLOAT DEFAULT 0.0,
                           price_15m FLOAT DEFAULT 0.0,
                           price_1h FLOAT DEFAULT 0.0,
                           price_4h FLOAT DEFAULT 0.0,
                           liquidity_5m FLOAT DEFAULT 0.0,
                           liquidity_15m FLOAT DEFAULT 0.0,
                           liquidity_1h FLOAT DEFAULT 0.0,
                           liquidity_4h FLOAT DEFAULT 0.0,
                           is_real_runner BOOLEAN DEFAULT FALSE
                        )"""
                    )
                )

    else:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session

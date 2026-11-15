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
            await conn.run_sync(Base.metadata.create_all)
    else:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session

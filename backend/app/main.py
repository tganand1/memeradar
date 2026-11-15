from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router, ws_router, auth_router
from app.api.auth import verify_token
from app.env import ENV
from app.bus import Broadcaster
from app.db.session import init_db
from app.runtime import Runtime, load_effective_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    config = await load_effective_config()
    bus = Broadcaster()
    runtime = Runtime(config, bus)
    app.state.runtime = runtime
    app.state.bus = bus
    await runtime.start()
    try:
        yield
    finally:
        await runtime.stop()


app = FastAPI(
    title="MemeRadar",
    description="24/7 Solana meme coin scanner + paper trading bot. PAPER TRADING ONLY.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if ENV.dashboard_auth_enabled:
        path = request.url.path
        if path.startswith("/api/") and not path.startswith("/api/auth/") and path != "/api/health":
            auth_header = request.headers.get("Authorization", "")
            token = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else request.query_params.get("token", "")
            if not verify_token(token):
                return Response("Unauthorized", status_code=401)
    return await call_next(request)


app.include_router(api_router)
app.include_router(auth_router)
app.include_router(ws_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "MemeRadar",
        "mode": "paper-trading-only",
        "docs": "/docs",
        "websocket": "/ws",
    }

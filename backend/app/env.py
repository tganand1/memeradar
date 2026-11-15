from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
load_dotenv(ENV_FILE)


@dataclass(frozen=True)
class Env:
    helius_api_key: str = ""
    rugcheck_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    database_url: str = ""
    mode: str = ""
    port: int = 8000
    dashboard_user: str = "admin"
    dashboard_password: str = ""

    @property
    def dashboard_auth_enabled(self) -> bool:
        return bool(self.dashboard_password)

    @property
    def helius_rpc_url(self) -> str:
        if not self.helius_api_key:
            return ""
        return f"https://mainnet.helius-rpc.com/?api-key={self.helius_api_key}"

    @property
    def helius_ws_url(self) -> str:
        if not self.helius_api_key:
            return ""
        return f"wss://mainnet.helius-rpc.com/?api-key={self.helius_api_key}"


def load_env() -> Env:
    return Env(
        helius_api_key=os.getenv("HELIUS_API_KEY", "").strip(),
        rugcheck_api_key=os.getenv("RUGCHECK_API_KEY", "").strip(),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        database_url=os.getenv("DATABASE_URL", "").strip(),
        mode=os.getenv("MEMERADAR_MODE", "").strip(),
        port=int(os.getenv("PORT", "8000") or 8000),
        dashboard_user=os.getenv("DASHBOARD_USER", "admin").strip() or "admin",
        dashboard_password=os.getenv("DASHBOARD_PASSWORD", "").strip(),
    )


ENV = load_env()

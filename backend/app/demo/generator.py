from __future__ import annotations

import random
import string
from datetime import datetime
from typing import Any

from app.analyzer.checks import build_demo_checks
from app.analyzer.types import NewToken
from app.utils import utcnow

BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

ADJECTIVES = [
    "Solar", "Turbo", "Cosmic", "Lunar", "Hyper", "Neon", "Quantum", "Feral", "Golden", "Rogue",
    "Electric", "Shadow", "Atomic", "Pixel", "Sonic", "Crimson", "Viral", "Mega", "Frosty", "Glitchy",
]
NOUNS = [
    "Pepe", "Doggo", "Chad", "Llama", "Rocket", "Squid", "Whale", "Goblin", "Panda", "Shark",
    "Frog", "Hamster", "Toaster", "Banana", "Penguin", "Sloth", "Wizard", "Potato", "Doge", "Crab",
]
TRENDS = ["2.0", "AI", "GPT", "X", "Prime", "Inu", "Coin", "Fi", "DAO", "Labs", "Rekt", "Moon"]
SOURCES = ["pump.fun", "pumpswap", "raydium", "pump.fun", "pump.fun"]


class DemoGenerator:
    """Generates believable new-token events without any API keys."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.supply = 1_000_000_000.0

    def random_address(self, size: int = 44) -> str:
        return "".join(self.rng.choice(BASE58) for _ in range(size))

    def _name(self) -> tuple[str, str]:
        adjective = self.rng.choice(ADJECTIVES)
        noun = self.rng.choice(NOUNS)
        if self.rng.random() < 0.35:
            name = f"{adjective} {noun} {self.rng.choice(TRENDS)}"
        else:
            name = f"{adjective} {noun}"
        symbol = (noun[:3] + adjective[:2]).upper()
        if self.rng.random() < 0.3:
            symbol = (noun[:4] + str(self.rng.randint(2, 99))).upper()
        return name, symbol

    def next_token(self) -> NewToken:
        archetype = self.rng.choices(["gem", "solid", "risky", "scam"], weights=[16, 32, 32, 20], k=1)[0]
        market_cap = min(1_500_000.0, max(6500.0, 10 ** self.rng.uniform(3.85, 5.95)))
        liquidity = max(900.0, market_cap * self.rng.uniform(0.12, 0.65))
        price = market_cap / self.supply
        name, symbol = self._name()
        checks, opportunity, hard, latent = build_demo_checks(archetype, self.rng, market_cap, liquidity, price)
        socials = checks["metadata"]["data"].get("socials", [])
        website = f"https://{symbol.lower()}.meme" if "website" in socials else None
        twitter = f"https://x.com/{symbol.lower()}" if "twitter" in socials else None
        telegram = f"https://t.me/{symbol.lower()}" if "telegram" in socials else None
        source = self.rng.choice(SOURCES)
        return NewToken(
            mint=self.random_address(),
            symbol=symbol,
            name=name,
            creator=self.random_address(),
            source=source,
            created_at=utcnow(),
            liquidity_usd=round(liquidity, 2),
            market_cap_usd=round(market_cap, 2),
            price_usd=price,
            image_url=f"https://api.dicebear.com/9.x/bottts-neutral/svg?seed={symbol}-{self.rng.randint(0, 9999)}",
            website=website,
            twitter=twitter,
            telegram=telegram,
            archetype=archetype,
            demo_profile={"checks": checks, "opportunity": opportunity, "hard": hard, "latent": latent},
            is_demo=True,
        )

    def synthetic_price_path(self, initial_price: float, points: int = 40, seconds: float = 12.0) -> list[dict[str, Any]]:
        now = utcnow()
        price = initial_price
        path: list[dict[str, Any]] = []
        for index in range(points):
            price *= 1.0 + self.rng.gauss(0.002, 0.03)
            path.append(
                {
                    "t": (now.timestamp() - (points - index) * seconds),
                    "p": price,
                }
            )
        return path


def random_mint(rng: random.Random | None = None) -> str:
    generator = rng or random.Random()
    return "".join(generator.choice(BASE58) for _ in range(44))


def symbol_from_mint(mint: str) -> str:
    return "".join(ch for ch in mint[:4] if ch in string.ascii_letters).upper() or "MEME"


def parse_created_at(value: Any) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value / 1000 if value > 1e12 else value)
    return utcnow()

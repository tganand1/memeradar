from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.analyzer.scoring import ScoreResult


@dataclass
class NewToken:
    mint: str
    symbol: str
    name: str
    creator: str | None
    source: str
    created_at: datetime
    liquidity_usd: float
    market_cap_usd: float
    price_usd: float
    image_url: str | None = None
    website: str | None = None
    twitter: str | None = None
    telegram: str | None = None
    archetype: str | None = None
    demo_profile: dict[str, Any] | None = None
    is_demo: bool = False


@dataclass
class Analysis:
    checks: dict[str, dict[str, Any]]
    opportunity_metrics: dict[str, dict[str, Any]]
    hard_data: dict[str, Any]
    scores: ScoreResult
    archetype: str = "unknown"
    quality: float = 0.0
    rug_probability: float = 0.0
    drift: float = 0.0
    volatility: float = 0.02
    flags: dict[str, Any] = field(default_factory=dict)

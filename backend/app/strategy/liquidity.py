from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LiquidityGate:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    liquidity_usd: float = 0.0
    detected_liquidity_usd: float = 0.0
    drop_pct: float = 0.0
    age_seconds: float = 0.0
    max_position_usd: float = 0.0


def check_liquidity(
    *,
    liquidity_usd: float,
    detected_liquidity_usd: float,
    age_seconds: float,
    min_liquidity_usd: float,
    max_drop_pct: float,
    max_age_seconds: float,
    max_pool_share_pct: float,
) -> LiquidityGate:
    """Hard gate applied immediately before a paper entry.

    Requires fresh, real pool liquidity; rejects thin pools, large drops since
    detection and stale price data.
    """
    liquidity = max(0.0, float(liquidity_usd or 0.0))
    detected = max(0.0, float(detected_liquidity_usd or 0.0))
    age = max(0.0, float(age_seconds or 0.0))
    drop = 0.0 if detected <= 0 else max(0.0, 1.0 - (liquidity / detected))
    max_position = liquidity * max(0.0, max_pool_share_pct)

    reasons: list[str] = []
    if liquidity <= 0:
        reasons.append("No fresh liquidity data available for this pool")
    elif liquidity < min_liquidity_usd:
        reasons.append(
            f"Liquidity ${liquidity:,.0f} is below the ${min_liquidity_usd:,.0f} minimum"
        )
    if detected > 0 and drop > max_drop_pct:
        reasons.append(
            f"Liquidity dropped {drop * 100:.1f}% since detection (limit {max_drop_pct * 100:.0f}%)"
        )
    if age > max_age_seconds:
        reasons.append(
            f"Price data is {age:.1f}s old (limit {max_age_seconds:.0f}s)"
        )
    if liquidity > 0 and max_position <= 0:
        reasons.append("Pool liquidity cap leaves no room for a position")

    return LiquidityGate(
        ok=not reasons,
        reasons=reasons,
        liquidity_usd=liquidity,
        detected_liquidity_usd=detected,
        drop_pct=drop,
        age_seconds=age,
        max_position_usd=max(0.0, max_position),
    )

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import StrategyCfg
from app.utils import clamp


@dataclass
class ScoreResult:
    safety_score: float
    opportunity_score: float
    final_score: float
    verdict: str
    hard_rejected: bool
    reject_reasons: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    green_flags: list[str] = field(default_factory=list)
    breakdown: dict[str, Any] = field(default_factory=dict)


def _weighted(checks: dict[str, dict[str, Any]], weights: dict[str, float]) -> tuple[float, dict[str, float]]:
    total = 0.0
    weighted = 0.0
    contributions: dict[str, float] = {}
    for check_id, check in checks.items():
        weight = float(weights.get(check_id, 0.0))
        if weight <= 0:
            continue
        total += weight
        contribution = weight * clamp(float(check.get("score", 0.0)), 0.0, 1.0)
        weighted += contribution
        contributions[check_id] = round(contribution, 2)
    if total <= 0:
        return 0.0, contributions
    return (weighted / total) * 100.0, contributions


def _opportunity_score(metrics: dict[str, dict[str, Any]], weights: dict[str, float]) -> tuple[float, dict[str, float]]:
    total = 0.0
    weighted = 0.0
    contributions: dict[str, float] = {}
    wash_penalty = 0.0
    for metric_id, metric in metrics.items():
        if metric_id == "wash":
            wash_penalty = clamp(float(metric.get("score", 0.0)), 0.0, 1.0) * 12.0
            continue
        weight = float(weights.get(metric_id, 0.0))
        if weight <= 0:
            continue
        total += weight
        contribution = weight * clamp(float(metric.get("score", 0.0)), 0.0, 1.0)
        weighted += contribution
        contributions[metric_id] = round(contribution, 2)
    base = (weighted / total) * 100.0 if total > 0 else 0.0
    adjusted = clamp(base - wash_penalty, 0.0, 100.0)
    if wash_penalty:
        contributions["wash_penalty"] = -round(wash_penalty, 2)
    return adjusted, contributions


def _collect_flags(checks: dict[str, dict[str, Any]], metrics: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    red: list[str] = []
    green: list[str] = []

    mint = checks.get("mint_authority", {})
    freeze = checks.get("freeze_authority", {})
    honeypot = checks.get("honeypot", {})
    liquidity = checks.get("liquidity", {})
    holders = checks.get("holders", {})
    creator = checks.get("creator", {})
    bundle = checks.get("bundle", {})
    lp_lock = checks.get("lp_lock", {})
    rugcheck = checks.get("rugcheck", {})
    metadata = checks.get("metadata", {})

    if mint.get("data", {}).get("authority"):
        red.append("Mint authority still active — supply can be inflated")
    elif mint.get("passed"):
        green.append("Mint authority revoked")

    if freeze.get("data", {}).get("authority"):
        red.append("Freeze authority active — holders can be frozen")
    elif freeze.get("passed"):
        green.append("Freeze authority revoked")

    if honeypot.get("data", {}).get("detected"):
        red.append("Honeypot detected — sell simulation failed")
    elif honeypot.get("data", {}).get("can_sell"):
        green.append("Sell simulation succeeded (not a honeypot)")

    top10 = float(holders.get("data", {}).get("top10_pct", 0.0))
    top1 = float(holders.get("data", {}).get("top1_pct", 0.0))
    holder_count = int(holders.get("data", {}).get("count", 0))
    if top10 >= 50:
        red.append(f"Top 10 wallets hold {top10:.1f}% of supply")
    elif top10 >= 35:
        red.append(f"Elevated holder concentration: top 10 hold {top10:.1f}%")
    elif top10 <= 20 and holder_count >= 50:
        green.append(f"Healthy holder distribution (top 10 {top10:.1f}%)")
    if top1 >= 22:
        red.append(f"Largest holder controls {top1:.1f}% of supply")
    if holder_count and holder_count < 25:
        red.append(f"Only {holder_count} holders — very early and fragile")
    elif holder_count >= 150:
        green.append(f"{holder_count} holders and growing")

    liq = float(liquidity.get("data", {}).get("usd", 0.0))
    if liq < 4000:
        red.append(f"Thin liquidity (${liq:,.0f}) — easy to drain")
    elif liq >= 25000:
        green.append(f"Deep liquidity (${liq:,.0f})")

    lp = lp_lock.get("data", {})
    if lp.get("burned"):
        green.append("LP burned")
    elif lp.get("locked_days", 0) >= 30:
        green.append(f"LP locked for {lp.get('locked_days')} days")
    elif not lp.get("burned") and lp.get("locked_days", 0) < 7:
        red.append("LP not burned or locked — rug liquidity risk")

    rugs = int(creator.get("data", {}).get("previous_rugs", 0))
    launched = int(creator.get("data", {}).get("tokens_launched", 0))
    if rugs >= 3:
        red.append(f"Creator rugged {rugs} previous tokens")
    elif rugs in (1, 2):
        red.append(f"Creator has {rugs} prior rug(s)")
    elif launched >= 0:
        green.append("Creator wallet has no rug history" if launched else "Fresh creator wallet")
    holds_pct = float(creator.get("data", {}).get("holds_pct", 0.0))
    if holds_pct >= 10:
        red.append(f"Creator still holds {holds_pct:.1f}% of supply")

    cluster = float(bundle.get("data", {}).get("cluster_pct", 0.0))
    snipers = int(bundle.get("data", {}).get("sniper_wallets", 0))
    if bundle.get("data", {}).get("available") is False:
        red.append("Bundle analysis unavailable — treating as neutral risk")
    elif cluster >= 20:
        red.append(f"Linked wallet cluster holds {cluster:.1f}% of supply")
    elif cluster >= 10:
        red.append(f"Possible bundled launch: cluster holds {cluster:.1f}%")
    elif cluster <= 5 and snipers <= 2:
        green.append("No meaningful bundle or sniper cluster")

    risk_flags = rugcheck.get("data", {}).get("risks", [])
    if risk_flags:
        red.append("RugCheck flags: " + ", ".join(str(flag) for flag in risk_flags[:3]))

    socials = int(metadata.get("data", {}).get("social_count", 0))
    if socials == 0:
        red.append("No website or social links")
    elif socials >= 2:
        green.append(f"{socials} official links present")
    if metadata.get("data", {}).get("duplicate_image"):
        red.append("Image duplicated from another token")
    if metadata.get("data", {}).get("copycat"):
        red.append("Name is a suspicious copycat of an existing token")

    momentum = metrics.get("momentum", {})
    if momentum.get("score", 0) >= 0.7:
        green.append("Strong early momentum")
    elif momentum.get("score", 1) <= 0.25:
        red.append("Momentum stalling or negative")

    volume = metrics.get("volume", {})
    if volume.get("score", 0) >= 0.7:
        green.append("High volume relative to liquidity")
    buy_pressure = metrics.get("buy_pressure", {})
    if buy_pressure.get("score", 0) >= 0.75:
        green.append("Aggressive buy pressure")
    wash = metrics.get("wash", {})
    if wash.get("score", 0) >= 0.6:
        red.append("Wash-trading pattern detected")

    return red, green


def score_token(
    checks: dict[str, dict[str, Any]],
    opportunity_metrics: dict[str, dict[str, Any]],
    config: StrategyCfg,
    hard_data: dict[str, Any],
) -> ScoreResult:
    """Combine weighted checks into safety, opportunity and final scores."""
    weights = dict(config.weights)
    safety, safety_contrib = _weighted(checks, weights)
    opportunity, opp_contrib = _opportunity_score(opportunity_metrics, config.opportunity_weights)
    final = clamp(
        safety * config.safety_weight + opportunity * config.opportunity_weight,
        0.0,
        100.0,
    )

    hard = config.hard_reject
    reject_reasons: list[str] = []
    liq = float(hard_data.get("liquidity_usd", 0.0))
    top10 = float(hard_data.get("top10_pct", 0.0))
    holders = int(hard_data.get("holders", 0))
    rugs = int(hard_data.get("creator_rugs", 0))

    if hard_data.get("mint_authority_revoked") is False:
        reject_reasons.append("Mint authority is active")
    elif hard_data.get("mint_authority_revoked") is None:
        reject_reasons.append("Mint authority could not be verified")
    if hard_data.get("freeze_authority_revoked") is False:
        reject_reasons.append("Freeze authority is active")
    elif hard_data.get("freeze_authority_revoked") is None:
        reject_reasons.append("Freeze authority could not be verified")
    if hard_data.get("honeypot") is True:
        reject_reasons.append("Honeypot detected (sell simulation failed)")
    if top10 > hard.top10_max_pct * 100:
        reject_reasons.append(f"Top 10 holders own {top10:.1f}% (> {hard.top10_max_pct * 100:.0f}%)")
    if rugs >= hard.creator_max_rugs:
        reject_reasons.append(f"Creator has {rugs} previous rugs")
    if liq < hard.min_liquidity_usd:
        reject_reasons.append(f"Liquidity ${liq:,.0f} below minimum ${hard.min_liquidity_usd:,.0f}")
    if holders and holders < hard.min_holders:
        reject_reasons.append(f"Only {holders} holders (< {hard.min_holders})")

    hard_rejected = bool(reject_reasons)
    red_flags, green_flags = _collect_flags(checks, opportunity_metrics)

    if hard_rejected:
        verdict = "AVOID"
    elif final >= config.min_score_buy:
        verdict = "BUY"
    elif final >= config.min_score_watch:
        verdict = "WATCH"
    else:
        verdict = "AVOID"

    breakdown = {
        "safety": round(safety, 2),
        "opportunity": round(opportunity, 2),
        "final": round(final, 2),
        "safety_weight": config.safety_weight,
        "opportunity_weight": config.opportunity_weight,
        "safety_contributions": safety_contrib,
        "opportunity_contributions": opp_contrib,
        "thresholds": {
            "buy": config.min_score_buy,
            "watch": config.min_score_watch,
        },
    }
    return ScoreResult(
        safety_score=round(safety, 2),
        opportunity_score=round(opportunity, 2),
        final_score=round(final, 2),
        verdict=verdict,
        hard_rejected=hard_rejected,
        reject_reasons=reject_reasons,
        red_flags=red_flags,
        green_flags=green_flags,
        breakdown=breakdown,
    )

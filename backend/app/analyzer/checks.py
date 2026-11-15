from __future__ import annotations

import math
import random
from typing import Any

from app.utils import clamp


def mk_check(
    check_id: str,
    name: str,
    score: float,
    passed: bool,
    value: str,
    detail: str,
    *,
    critical: bool = False,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "name": name,
        "score": round(clamp(score, 0.0, 1.0), 4),
        "passed": bool(passed),
        "critical": critical,
        "value": value,
        "detail": detail,
        "data": data or {},
    }


def mk_metric(metric_id: str, name: str, score: float, value: str, detail: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": metric_id,
        "name": name,
        "score": round(clamp(score, 0.0, 1.0), 4),
        "value": value,
        "detail": detail,
        "data": data or {},
    }


def liquidity_score(usd: float) -> float:
    if usd <= 2000:
        return 0.0
    return clamp((math.log10(usd) - math.log10(2000)) / (math.log10(150000) - math.log10(2000)), 0.0, 1.0)


def lp_score(burned: bool, locked_days: int) -> float:
    if burned:
        return 1.0
    if locked_days >= 30:
        return 0.85
    if locked_days >= 7:
        return 0.6
    if locked_days > 0:
        return 0.35
    return 0.05


def holders_score(top10: float, top1: float, count: int) -> float:
    top10_score = clamp(1.0 - (top10 - 0.15) / 0.55, 0.0, 1.0)
    top1_score = clamp(1.0 - (top1 - 0.05) / 0.35, 0.0, 1.0)
    count_score = clamp((math.log10(max(count, 1)) - 1.2) / 1.8, 0.0, 1.0)
    return 0.5 * top10_score + 0.25 * top1_score + 0.25 * count_score


def creator_score(rugs: int, launched: int, holds_pct: float) -> float:
    base = {0: 1.0, 1: 0.72, 2: 0.45, 3: 0.12}.get(rugs, 0.0)
    if launched >= 8:
        base *= 0.75
    if holds_pct >= 10:
        base *= 0.6
    elif holds_pct >= 5:
        base *= 0.8
    return clamp(base, 0.0, 1.0)


def bundle_score(cluster_pct: float, snipers: int, available: bool = True) -> float:
    if not available:
        return 0.5
    base = clamp(1.0 - (cluster_pct - 2.0) / 38.0, 0.0, 1.0)
    base -= min(0.25, snipers * 0.03)
    return clamp(base, 0.0, 1.0)


def rugcheck_score(normalized: float, risk_count: int) -> float:
    return clamp(normalized / 100.0 - risk_count * 0.04, 0.0, 1.0)


def metadata_score(socials: int, duplicate: bool, copycat: bool) -> float:
    base = clamp(socials / 3.0, 0.0, 1.0)
    if duplicate:
        base -= 0.35
    if copycat:
        base -= 0.25
    return clamp(base, 0.0, 1.0)


def build_demo_checks(
    archetype: str, rng: random.Random, mcap: float, liquidity: float, price: float
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Create a coherent set of demo checks, opportunity metrics and latent price behaviour."""
    if archetype == "gem":
        mint_revoked, freeze_revoked = True, True
        top10 = rng.uniform(0.12, 0.245)
        top1 = rng.uniform(0.04, 0.11)
        holders = rng.randint(160, 1500)
        rugs = 0
        launched = rng.randint(0, 6)
        holds = rng.uniform(0.0, 2.5)
        burned = rng.random() < 0.75
        locked_days = 0 if burned else rng.choice([30, 60, 90, 180])
        snipers = rng.randint(0, 2)
        cluster = rng.uniform(0.5, 6.0)
        rug_norm = rng.uniform(78, 97)
        risks: list[str] = []
        socials = 3 if rng.random() < 0.7 else 2
        duplicate, copycat = False, False
        buy_sell = rng.uniform(1.6, 3.2)
        unique_buyers = rng.randint(120, 700)
        vol_liq = rng.uniform(1.0, 5.0)
        change5 = rng.uniform(15, 120)
        wash = rng.uniform(0.02, 0.18)
        honeypot = False
        quality, rug_prob, drift, vol = rng.uniform(0.75, 0.98), 0.05, rng.uniform(0.0005, 0.0011), rng.uniform(0.02, 0.035)
    elif archetype == "solid":
        strong = rng.random() < 0.5
        mint_revoked = True
        freeze_revoked = rng.random() < 0.96
        top10 = rng.uniform(0.14, 0.26) if strong else rng.uniform(0.20, 0.35)
        top1 = rng.uniform(0.05, 0.12) if strong else rng.uniform(0.07, 0.17)
        holders = rng.randint(110, 620) if strong else rng.randint(45, 340)
        rugs = 0 if rng.random() < (0.94 if strong else 0.85) else 1
        launched = rng.randint(0, 6) if strong else rng.randint(1, 8)
        holds = rng.uniform(0.0, 3.0) if strong else rng.uniform(0.0, 6.0)
        burned = rng.random() < (0.7 if strong else 0.45)
        locked_days = 0 if burned else rng.choice([7, 30, 60] if strong else [0, 7, 30, 60])
        snipers = rng.randint(0, 2) if strong else rng.randint(1, 5)
        cluster = rng.uniform(0.8, 6.0) if strong else rng.uniform(3.0, 11.0)
        rug_norm = rng.uniform(76, 92) if strong else rng.uniform(55, 82)
        risks = ["LP not locked"] if locked_days == 0 and not burned else []
        socials = rng.randint(2, 3) if strong else rng.randint(1, 3)
        duplicate = rng.random() < 0.02 if strong else rng.random() < 0.05
        copycat = rng.random() < 0.03 if strong else rng.random() < 0.08
        buy_sell = rng.uniform(1.3, 2.6) if strong else rng.uniform(1.05, 2.2)
        unique_buyers = rng.randint(90, 420) if strong else rng.randint(30, 220)
        vol_liq = rng.uniform(0.7, 2.6) if strong else rng.uniform(0.35, 1.8)
        change5 = rng.uniform(5, 80) if strong else rng.uniform(-12, 65)
        wash = rng.uniform(0.04, 0.2) if strong else rng.uniform(0.1, 0.35)
        honeypot = False
        if strong:
            quality, rug_prob, drift, vol = rng.uniform(0.58, 0.82), 0.1, rng.uniform(0.0002, 0.0007), rng.uniform(0.022, 0.04)
        else:
            quality, rug_prob, drift, vol = rng.uniform(0.35, 0.62), 0.16, rng.uniform(0.00005, 0.0005), rng.uniform(0.025, 0.045)
    elif archetype == "risky":
        mint_revoked = rng.random() < 0.9
        freeze_revoked = rng.random() < 0.85
        top10 = rng.uniform(0.34, 0.54)
        top1 = rng.uniform(0.12, 0.28)
        holders = rng.randint(18, 130)
        rugs = rng.choice([1, 1, 2])
        launched = rng.randint(2, 10)
        holds = rng.uniform(4, 16)
        burned = False
        locked_days = rng.choice([0, 0, 0, 7])
        snipers = rng.randint(3, 9)
        cluster = rng.uniform(9.0, 21.0)
        rug_norm = rng.uniform(28, 58)
        risks = rng.sample(["Low liquidity", "Top holders own a large share", "Creator history", "No LP lock"], k=rng.randint(1, 3))
        socials = rng.randint(0, 2)
        duplicate = rng.random() < 0.15
        copycat = rng.random() < 0.2
        buy_sell = rng.uniform(0.65, 1.4)
        unique_buyers = rng.randint(10, 70)
        vol_liq = rng.uniform(0.08, 0.8)
        change5 = rng.uniform(-45, 25)
        wash = rng.uniform(0.3, 0.7)
        honeypot = False
        quality, rug_prob, drift, vol = rng.uniform(-0.15, 0.15), 0.32, rng.uniform(-0.0004, 0.0001), rng.uniform(0.03, 0.06)
    else:
        mint_revoked = rng.random() < 0.55
        freeze_revoked = rng.random() < 0.6
        top10 = rng.uniform(0.52, 0.86)
        top1 = rng.uniform(0.18, 0.5)
        holders = rng.randint(3, 45)
        rugs = rng.randint(3, 6)
        launched = rng.randint(4, 14)
        holds = rng.uniform(8, 30)
        burned = False
        locked_days = 0
        snipers = rng.randint(6, 18)
        cluster = rng.uniform(20, 60)
        rug_norm = rng.uniform(4, 32)
        risks = rng.sample(
            ["Honeypot risk", "Mint authority active", "Top holders own a large share", "Creator rugged before", "Low liquidity"],
            k=rng.randint(2, 4),
        )
        socials = rng.randint(0, 1)
        duplicate = rng.random() < 0.3
        copycat = rng.random() < 0.4
        buy_sell = rng.uniform(0.35, 1.1)
        unique_buyers = rng.randint(3, 30)
        vol_liq = rng.uniform(0.03, 0.5)
        change5 = rng.uniform(-75, 15)
        wash = rng.uniform(0.45, 0.95)
        honeypot = rng.random() < 0.32
        quality, rug_prob, drift, vol = rng.uniform(-0.9, -0.3), 0.65, rng.uniform(-0.0009, -0.0002), rng.uniform(0.04, 0.08)

    liquidity = max(500.0, liquidity)
    mcap = max(mcap, liquidity * 1.2)
    mcap_liq = mcap / max(liquidity, 1.0)
    change5 = round(change5, 1)
    vol_liq = round(vol_liq, 2)
    wash = clamp(wash, 0.0, 1.0)
    social_list = ["website", "twitter", "telegram"][:socials]
    socials_text = ", ".join(social_list) if social_list else "none"

    checks: dict[str, Any] = {}
    checks["mint_authority"] = mk_check(
        "mint_authority",
        "Mint authority revoked",
        1.0 if mint_revoked else 0.0,
        mint_revoked,
        "Revoked" if mint_revoked else "ACTIVE",
        "Mint authority is renounced." if mint_revoked else "Mint authority is still active — the creator can mint unlimited supply.",
        critical=True,
        data={"authority": None if mint_revoked else "creator"},
    )
    checks["freeze_authority"] = mk_check(
        "freeze_authority",
        "Freeze authority revoked",
        1.0 if freeze_revoked else 0.0,
        freeze_revoked,
        "Revoked" if freeze_revoked else "ACTIVE",
        "Freeze authority is renounced." if freeze_revoked else "Freeze authority active — wallets can be frozen at will.",
        critical=True,
        data={"authority": None if freeze_revoked else "creator"},
    )
    liq_score = liquidity_score(liquidity)
    checks["liquidity"] = mk_check(
        "liquidity",
        "Liquidity depth",
        liq_score,
        liquidity >= 4000,
        f"${liquidity:,.0f}",
        f"${liquidity:,.0f} in the pool; ~{mcap_liq:.1f}x market cap to liquidity.",
        data={"usd": round(liquidity, 2), "mcap_liq_ratio": round(mcap_liq, 2)},
    )
    lp = lp_score(burned, locked_days)
    checks["lp_lock"] = mk_check(
        "lp_lock",
        "LP burned / locked",
        lp,
        burned or locked_days >= 7,
        "Burned" if burned else (f"Locked {locked_days}d" if locked_days else "Unlocked"),
        "Liquidity pool tokens are burned." if burned else (
            f"LP tokens locked for {locked_days} days." if locked_days else "LP tokens are unlocked — liquidity can be pulled at any moment."
        ),
        data={"burned": burned, "locked_days": locked_days},
    )
    holder_count = holders
    hscore = holders_score(top10 * 100, top1 * 100, holder_count)
    checks["holders"] = mk_check(
        "holders",
        "Holder distribution",
        hscore,
        top10 < 0.35 and holder_count >= 25,
        f"top10 {top10 * 100:.1f}%",
        f"{holder_count} holders; top wallet {top1 * 100:.1f}%, top 10 hold {top10 * 100:.1f}% (pool & curve excluded).",
        data={
            "top10_pct": round(top10 * 100, 2),
            "top1_pct": round(top1 * 100, 2),
            "count": holder_count,
            "growth_pct": round(rng.uniform(2, 25), 1),
        },
    )
    cscore = creator_score(rugs, launched, holds)
    checks["creator"] = mk_check(
        "creator",
        "Creator wallet history",
        cscore,
        rugs < 3 and holds < 10,
        f"{rugs} prior rugs",
        f"Wallet launched {launched} tokens, {rugs} rugged; currently holds {holds:.1f}% of supply.",
        data={
            "tokens_launched": launched,
            "previous_rugs": rugs,
            "holds_pct": round(holds, 2),
            "wallet": "DemoWallet" + str(rng.randint(1000, 9999)),
        },
    )
    bscore = bundle_score(cluster, snipers)
    checks["bundle"] = mk_check(
        "bundle",
        "Bundle / sniper detection",
        bscore,
        cluster < 15 and snipers <= 5,
        f"{cluster:.1f}% clustered",
        f"{snipers} sniper wallets in the first slots; linked-wallet cluster holds {cluster:.1f}% of supply.",
        data={"cluster_pct": round(cluster, 2), "sniper_wallets": snipers, "available": True},
    )
    checks["honeypot"] = mk_check(
        "honeypot",
        "Honeypot / sell-ability",
        0.0 if honeypot else 1.0,
        not honeypot,
        "FAILED" if honeypot else "Can sell",
        "Sell simulation reverted — buys only." if honeypot else "Simulated sell quote succeeded; token is sellable.",
        critical=True,
        data={"detected": honeypot, "can_sell": not honeypot},
    )
    rc_score = rugcheck_score(rug_norm, len(risks))
    checks["rugcheck"] = mk_check(
        "rugcheck",
        "RugCheck.xyz risk",
        rc_score,
        rug_norm >= 60 and not risks,
        f"{rug_norm:.0f}/100",
        f"RugCheck normalised safety score {rug_norm:.0f}/100; {len(risks)} risk flag(s).",
        data={"score": round(rug_norm, 1), "risks": risks},
    )
    mscore = metadata_score(socials, duplicate, copycat)
    checks["metadata"] = mk_check(
        "metadata",
        "Metadata & socials",
        mscore,
        socials >= 1 and not duplicate and not copycat,
        f"{socials}/3 links",
        f"Official links: {socials_text}." + (" Image duplicated." if duplicate else "") + (" Copycat name." if copycat else ""),
        data={
            "social_count": socials,
            "socials": social_list,
            "duplicate_image": duplicate,
            "copycat": copycat,
        },
    )

    trade_score = clamp(
        0.4 * clamp((buy_sell - 0.5) / 2.0, 0.0, 1.0)
        + 0.3 * clamp(math.log10(max(unique_buyers, 1)) / 2.7, 0.0, 1.0)
        + 0.3 * (1.0 - wash),
        0.0,
        1.0,
    )
    checks["trading"] = mk_check(
        "trading",
        "Early trading behaviour",
        trade_score,
        buy_sell >= 1.0 and wash < 0.6,
        f"B/S {buy_sell:.2f}",
        f"Buy/sell ratio {buy_sell:.2f}, {unique_buyers} unique buyers, wash-trading signal {wash * 100:.0f}%.",
        data={
            "buy_sell_ratio": round(buy_sell, 2),
            "unique_buyers": unique_buyers,
            "wash_pct": round(wash * 100, 1),
        },
    )
    mom_score = clamp(
        0.6 * clamp((change5 + 30) / 120.0, 0.0, 1.0)
        + 0.4 * clamp((vol_liq - 0.1) / 2.5, 0.0, 1.0),
        0.0,
        1.0,
    )
    checks["momentum"] = mk_check(
        "momentum",
        "Momentum",
        mom_score,
        change5 > 0 and vol_liq > 0.3,
        f"{change5:+.1f}% / 5m",
        f"Price {change5:+.1f}% in the first minutes; volume/liquidity {vol_liq:.2f}x.",
        data={"change_5m_pct": change5, "volume_liquidity_ratio": vol_liq},
    )

    opportunity: dict[str, Any] = {}
    opportunity["momentum"] = mk_metric(
        "momentum",
        "Momentum",
        clamp((change5 + 30) / 120.0, 0.0, 1.0),
        f"{change5:+.1f}%",
        "Price change in the first minutes.",
        {"change_5m_pct": change5},
    )
    opportunity["volume"] = mk_metric(
        "volume",
        "Volume acceleration",
        clamp((vol_liq - 0.1) / 2.8, 0.0, 1.0),
        f"{vol_liq:.2f}x",
        "Volume relative to pool liquidity.",
        {"volume_liquidity_ratio": vol_liq},
    )
    opportunity["buyers"] = mk_metric(
        "buyers",
        "Unique buyer growth",
        clamp(math.log10(max(unique_buyers, 1)) / 2.7, 0.0, 1.0),
        f"{unique_buyers}",
        "Distinct wallets that bought so far.",
        {"unique_buyers": unique_buyers},
    )
    opportunity["buy_pressure"] = mk_metric(
        "buy_pressure",
        "Buy pressure",
        clamp((buy_sell - 0.5) / 2.2, 0.0, 1.0),
        f"{buy_sell:.2f}",
        "Aggregated buy/sell transaction ratio.",
        {"buy_sell_ratio": buy_sell},
    )
    opportunity["mcap_liquidity"] = mk_metric(
        "mcap_liquidity",
        "Market cap vs liquidity",
        clamp(1.0 - (mcap_liq - 2.0) / 25.0, 0.0, 1.0),
        f"{mcap_liq:.1f}x",
        "Lower market-cap-to-liquidity is healthier.",
        {"mcap_liq_ratio": round(mcap_liq, 2)},
    )
    opportunity["wash"] = mk_metric(
        "wash",
        "Wash-trading signal",
        wash,
        f"{wash * 100:.0f}%",
        "Higher means more repeated wallet churn (penalty).",
        {"wash_pct": round(wash * 100, 1)},
    )

    hard = {
        "mint_authority_revoked": mint_revoked,
        "freeze_authority_revoked": freeze_revoked,
        "honeypot": honeypot,
        "top10_pct": round(top10 * 100, 2),
        "top1_pct": round(top1 * 100, 2),
        "liquidity_usd": liquidity,
        "holders": holder_count,
        "creator_rugs": rugs,
    }
    latent = {
        "quality": round(quality, 3),
        "rug_probability": rug_prob,
        "drift": drift,
        "volatility": vol,
    }
    return checks, opportunity, hard, latent

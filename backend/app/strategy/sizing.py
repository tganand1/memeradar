from __future__ import annotations

from dataclasses import dataclass, field

from app.config import PaperSection, StrategyCfg
from app.utils import clamp


@dataclass
class SizingResult:
    usd: float
    skipped: bool
    skip_reason: str | None = None
    reasons: list[str] = field(default_factory=list)
    caps: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


def compute_position_size(
    *,
    equity: float,
    cash: float,
    open_value: float,
    liquidity_usd: float,
    score: float,
    safety: float,
    opportunity: float,
    streak_mult: float,
    config: StrategyCfg,
    paper: PaperSection,
) -> SizingResult:
    """Score + confidence sizing with fractional-Kelly safety and hard caps."""
    if equity <= 0:
        return SizingResult(0.0, True, "Account equity is zero", metrics={"equity": 0.0})

    threshold = config.min_score_buy
    score_norm = clamp((score - threshold) / max(1.0, 100.0 - threshold), 0.0, 1.0)
    confidence = clamp(0.5 * (safety / 100.0) + 0.5 * (opportunity / 100.0), 0.0, 1.0)
    sizing = config.sizing

    base = equity * sizing.base_pct_of_equity
    score_mult = 0.5 + sizing.score_scale * score_norm
    conf_mult = sizing.confidence_floor + (sizing.confidence_ceiling - sizing.confidence_floor) * confidence
    streak = clamp(streak_mult, sizing.min_streak_mult, sizing.max_streak_mult)
    raw = base * score_mult * conf_mult * streak

    p = 0.52 + 0.40 * score_norm
    b = max(0.1, sizing.kelly_payoff)
    kelly_f = max(0.0, (p * (b + 1.0) - 1.0) / b)
    kelly_cap = equity * kelly_f * sizing.kelly_fraction

    position_cap = equity * paper.max_position_pct
    liquidity_cap = max(0.0, liquidity_usd) * paper.max_pool_share_pct
    exposure_cap = max(0.0, equity * paper.max_open_exposure_pct - open_value)
    cash_cap = max(0.0, cash - equity * paper.cash_reserve_pct)

    caps = [
        ("max position %", position_cap),
        ("pool liquidity share", liquidity_cap),
        ("open exposure", exposure_cap),
        ("cash reserve", cash_cap),
        ("fractional Kelly", kelly_cap),
    ]
    final = min(raw, *[value for _name, value in caps])
    final = round(max(0.0, final), 2)

    reasons = [
        f"Base size {sizing.base_pct_of_equity * 100:.1f}% of ${equity:,.2f} equity = ${base:,.2f}",
        f"Score {score:.1f} vs {threshold:.0f} buy threshold → ×{score_mult:.2f}",
        f"Confidence {confidence * 100:.0f}% (safety {safety:.0f}, momentum {opportunity:.0f}) → ×{conf_mult:.2f}",
        f"Streak multiplier ×{streak:.2f}",
        f"Fractional Kelly safety cap {kelly_f * sizing.kelly_fraction * 100:.2f}% of equity (Kelly fraction {sizing.kelly_fraction:.2f})",
        f"Applied caps: 10% max position, {paper.max_pool_share_pct * 100:.1f}% of ${liquidity_usd:,.0f} liquidity, "
        f"{paper.max_open_exposure_pct * 100:.0f}% max exposure, {paper.cash_reserve_pct * 100:.0f}% cash reserve",
    ]

    skipped = False
    skip_reason: str | None = None
    if final < paper.min_trade_usd:
        skipped = True
        skip_reason = (
            f"Computed size ${final:,.2f} below minimum ${paper.min_trade_usd:,.2f} "
            f"(tightest cap: {min(caps, key=lambda item: item[1])[0]})"
        )

    return SizingResult(
        usd=final,
        skipped=skipped,
        skip_reason=skip_reason,
        reasons=reasons,
        caps=[f"{name}: ${value:,.2f}" for name, value in caps],
        metrics={
            "equity": round(equity, 2),
            "base": round(base, 2),
            "score_mult": round(score_mult, 3),
            "confidence_mult": round(conf_mult, 3),
            "confidence": round(confidence, 3),
            "streak_mult": round(streak, 3),
            "kelly_fraction_full": round(kelly_f, 4),
            "kelly_cap": round(kelly_cap, 2),
            "raw": round(raw, 2),
            "final": final,
            "liquidity_cap": round(liquidity_cap, 2),
            "position_cap": round(position_cap, 2),
            "exposure_cap": round(exposure_cap, 2),
            "cash_cap": round(cash_cap, 2),
        },
    )


def streak_multiplier(win_streak: int, loss_streak: int, config: StrategyCfg) -> float:
    sizing = config.sizing
    if loss_streak > 0:
        return clamp(sizing.losing_streak_cut ** loss_streak, sizing.min_streak_mult, 1.0)
    if win_streak > 0:
        return clamp(sizing.winning_streak_boost ** win_streak, 1.0, sizing.max_streak_mult)
    return 1.0

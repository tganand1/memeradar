from __future__ import annotations

from dataclasses import dataclass, field

from app.analyzer.types import Analysis
from app.config import PaperSection, StrategyCfg
from app.strategy.liquidity import LiquidityGate
from app.strategy.sizing import SizingResult, compute_position_size, streak_multiplier


@dataclass
class Decision:
    action: str
    reasons: list[str] = field(default_factory=list)
    summary: str = ""
    sizing: SizingResult | None = None


def decide(
    analysis: Analysis,
    *,
    config: StrategyCfg,
    paper: PaperSection,
    equity: float,
    cash: float,
    open_value: float,
    win_streak: int,
    loss_streak: int,
    bot_enabled: bool,
    breaker_reason: str | None = None,
    liquidity_usd: float | None = None,
    liquidity_gate: LiquidityGate | None = None,
    open_positions: int = 0,
) -> Decision:
    scores = analysis.scores
    symbol = analysis.flags.get("symbol", "token") if analysis.flags else "token"
    if not bot_enabled:
        return Decision("SKIP", ["Bot is paused — no new entries"], "Bot paused")
    if breaker_reason:
        return Decision("SKIP", [breaker_reason], "Circuit breaker active")
    if open_positions >= paper.max_open_positions:
        return Decision(
            "SKIP",
            [f"Max open positions reached ({paper.max_open_positions}) — close a position to open new ones"],
            f"Max positions ({paper.max_open_positions})",
        )
    if scores.verdict != "BUY":
        reasons = [f"Verdict {scores.verdict}: final score {scores.final_score:.1f} (buy ≥ {config.min_score_buy:.0f})"]
        reasons.extend(scores.reject_reasons[:4])
        reasons.extend(scores.red_flags[:4])
        return Decision("SKIP", reasons, f"{scores.verdict} — score {scores.final_score:.1f}")

    if liquidity_gate is not None and not liquidity_gate.ok:
        return Decision(
            "SKIP",
            list(liquidity_gate.reasons),
            "Liquidity gate blocked entry",
        )

    effective_liquidity = (
        liquidity_usd
        if liquidity_usd is not None
        else float(analysis.hard_data.get("liquidity_usd", 0.0) or 0.0)
    )
    sizing = compute_position_size(
        equity=equity,
        cash=cash,
        open_value=open_value,
        liquidity_usd=effective_liquidity,
        score=scores.final_score,
        safety=scores.safety_score,
        opportunity=scores.opportunity_score,
        streak_mult=streak_multiplier(win_streak, loss_streak, config),
        config=config,
        paper=paper,
    )
    buy_reasons = [
        f"Final score {scores.final_score:.1f} (safety {scores.safety_score:.0f} / momentum {scores.opportunity_score:.0f})",
        *scores.green_flags[:5],
        *sizing.reasons,
    ]
    if liquidity_gate is not None:
        buy_reasons.insert(
            1,
            f"Entry liquidity ${liquidity_gate.liquidity_usd:,.0f} "
            f"({liquidity_gate.age_seconds:.1f}s old, "
            f"{liquidity_gate.drop_pct * 100:+.1f}% since detection)",
        )
    if sizing.skipped:
        return Decision("SKIP", [sizing.skip_reason or "Sizing skipped the trade"], "Sizing below minimum", sizing)
    return Decision("BUY", buy_reasons, f"BUY ${sizing.usd:,.2f} — score {scores.final_score:.0f}", sizing)

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.config import StrategyCfg


@dataclass
class ExitAction:
    kind: str
    reason: str
    sell_all: bool = False
    fraction_of_original: float = 0.0
    zero_proceeds: bool = False
    activates_trailing: bool = False
    tp_index: int | None = None


@dataclass
class ExitPlan:
    actions: list[ExitAction] = field(default_factory=list)
    emergency: bool = False

    @property
    def has_actions(self) -> bool:
        return bool(self.actions)


def evaluate_exit(
    position: dict,
    config: StrategyCfg,
    now: datetime,
    flags: dict | None = None,
) -> ExitPlan:
    """Evaluate stop loss, staged take profits, trailing stop, time stop and emergencies."""
    flags = flags or {}
    if position.get("tokens_remaining", 0) <= 0:
        return ExitPlan()

    entry = float(position["entry_price"])
    current = float(position.get("current_price") or entry)
    peak = float(position.get("peak_price") or current)
    remaining = float(position["tokens_remaining"])
    original = float(position.get("token_amount") or remaining)
    gain = (current / entry - 1.0) if entry > 0 else 0.0
    exits = config.exits

    if flags.get("rugged") or position.get("rugged") or current <= 0:
        return ExitPlan(
            actions=[ExitAction("rug", "Token rugged — liquidity gone, position wiped out", sell_all=True, zero_proceeds=True)],
            emergency=True,
        )

    liquidity_entry = float(position.get("liquidity_at_entry") or 0.0)
    liquidity_now = float(flags.get("liquidity_usd") or position.get("liquidity_now") or liquidity_entry)
    if liquidity_entry > 0 and liquidity_now < liquidity_entry * (1.0 - exits.emergency_liquidity_drop_pct):
        drop = (1.0 - liquidity_now / liquidity_entry) * 100.0
        return ExitPlan(
            actions=[ExitAction("emergency", f"Liquidity drained {drop:.0f}% — emergency exit", sell_all=True)],
            emergency=True,
        )
    if flags.get("creator_sold"):
        return ExitPlan(
            actions=[ExitAction("emergency", "Creator wallet sold its supply — emergency exit", sell_all=True)],
            emergency=True,
        )
    if flags.get("top_holders_dump"):
        return ExitPlan(
            actions=[ExitAction("emergency", "Top holders are dumping — emergency exit", sell_all=True)],
            emergency=True,
        )

    if gain <= exits.stop_loss_pct:
        return ExitPlan(
            actions=[ExitAction("stop_loss", f"Stop loss hit at {gain * 100:.1f}% (limit {exits.stop_loss_pct * 100:.0f}%)", sell_all=True)],
            emergency=True,
        )

    actions: list[ExitAction] = []
    tp_taken = set(position.get("tp_taken") or [])
    for index, level in enumerate(exits.take_profits):
        if index in tp_taken:
            continue
        if gain >= level.gain_pct:
            fraction = max(0.0, min(1.0, level.sell_fraction))
            actions.append(
                ExitAction(
                    kind="take_profit",
                    reason=f"Take profit stage {index + 1} at +{gain * 100:.0f}% (target +{level.gain_pct * 100:.0f}%, selling {fraction * 100:.0f}%)",
                    fraction_of_original=fraction,
                    activates_trailing=True,
                    tp_index=index,
                )
            )
    if actions:
        return ExitPlan(actions=actions)

    if position.get("trailing_active") and peak > 0 and current <= peak * (1.0 - exits.trailing_stop_pct):
        drawdown = (1.0 - current / peak) * 100.0
        return ExitPlan(
            actions=[
                ExitAction(
                    "trailing_stop",
                    f"Trailing stop: {drawdown:.0f}% off peak ${peak:.8f} (limit {exits.trailing_stop_pct * 100:.0f}%)",
                    sell_all=True,
                )
            ],
            emergency=True,
        )

    opened_at: datetime = position.get("opened_at") or now
    hold_minutes = max(0.0, (now - opened_at).total_seconds() / 60.0)
    if hold_minutes >= exits.time_stop_minutes and gain <= exits.time_stop_min_gain_pct:
        return ExitPlan(
            actions=[
                ExitAction(
                    "time_stop",
                    f"Time stop after {hold_minutes:.0f} min — still {gain * 100:+.1f}%",
                    sell_all=True,
                )
            ]
        )

    if len(tp_taken) < len(exits.take_profits) and original > remaining:
        pass

    return ExitPlan()

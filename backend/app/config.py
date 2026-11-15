from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"


class AppSection(BaseModel):
    mode: Literal["demo", "live"] = "live"
    log_level: str = "INFO"
    demo_seed: bool = True
    sol_price_usd: float = 190.0


class PaperSection(BaseModel):
    starting_balance: float = 100.0
    min_trade_usd: float = 1.0
    max_position_pct: float = 0.05
    max_open_exposure_pct: float = 0.60
    max_open_positions: int = 6
    cash_reserve_pct: float = 0.10
    max_pool_share_pct: float = 0.015
    taker_fee_pct: float = 0.006
    priority_fee_sol: float = 0.0008
    jito_tip_sol: float = 0.0012
    random_slippage_min_pct: float = 0.01
    random_slippage_max_pct: float = 0.05
    execution_delay_min_ms: int = 400
    execution_delay_max_ms: int = 1500
    failed_tx_rate: float = 0.12
    sell_failed_tx_rate: float = 0.10
    mark_haircut_pct: float = 0.02
    equity_snapshot_seconds: int = 5


class HardReject(BaseModel):
    top10_max_pct: float = 0.50
    top1_max_pct: float = 0.22
    min_liquidity_usd: float = 3000.0
    liquidity_drop_max_pct: float = 0.20
    max_price_age_seconds: float = 15.0
    creator_max_rugs: int = 3
    min_holders: int = 25


class SizingCfg(BaseModel):
    base_pct_of_equity: float = 0.04
    score_scale: float = 1.5
    confidence_floor: float = 0.7
    confidence_ceiling: float = 1.3
    kelly_fraction: float = 0.30
    kelly_payoff: float = 1.0
    losing_streak_cut: float = 0.75
    winning_streak_boost: float = 1.12
    max_streak_mult: float = 1.5
    min_streak_mult: float = 0.45


class TakeProfit(BaseModel):
    gain_pct: float = 1.0
    sell_fraction: float = 0.5


class ExitsCfg(BaseModel):
    stop_loss_pct: float = -0.25
    take_profits: list[TakeProfit] = Field(
        default_factory=lambda: [TakeProfit(gain_pct=1.0, sell_fraction=0.5), TakeProfit(gain_pct=3.0, sell_fraction=0.5)]
    )
    trailing_stop_pct: float = 0.30
    time_stop_minutes: int = 45
    time_stop_min_gain_pct: float = 0.0
    emergency_liquidity_drop_pct: float = 0.30


class CircuitBreaker(BaseModel):
    daily_loss_limit_pct: float = 0.15


class StrategyCfg(BaseModel):
    min_score_buy: float = 55.0
    min_score_watch: float = 45.0
    min_token_age_seconds: int = 120
    safety_weight: float = 0.55
    opportunity_weight: float = 0.45
    hard_reject: HardReject = Field(default_factory=HardReject)
    sizing: SizingCfg = Field(default_factory=SizingCfg)
    exits: ExitsCfg = Field(default_factory=ExitsCfg)
    circuit_breaker: CircuitBreaker = Field(default_factory=CircuitBreaker)
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "mint_authority": 14.0,
            "freeze_authority": 12.0,
            "liquidity": 12.0,
            "lp_lock": 8.0,
            "holders": 14.0,
            "creator": 10.0,
            "bundle": 8.0,
            "honeypot": 14.0,
            "rugcheck": 5.0,
            "metadata": 3.0,
        }
    )
    opportunity_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "momentum": 30.0,
            "volume": 25.0,
            "buyers": 20.0,
            "buy_pressure": 15.0,
            "mcap_liquidity": 10.0,
        }
    )


class ListenerCfg(BaseModel):
    demo_token_interval_seconds: float = 7.0
    demo_token_jitter_seconds: float = 3.0
    dexscreener_poll_seconds: float = 8.0
    geckoterminal_poll_seconds: float = 30.0
    price_poll_seconds: float = 5.0
    position_price_poll_seconds: float = 4.0
    max_tokens_per_minute: int = 90


class NotifierCfg(BaseModel):
    enabled: bool = False
    notify_buys: bool = True
    notify_sells: bool = True
    notify_big_wins: bool = True
    big_win_usd: float = 10.0
    notify_errors: bool = True


class ApiCfg(BaseModel):
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])


class AppConfig(BaseModel):
    app: AppSection = Field(default_factory=AppSection)
    paper: PaperSection = Field(default_factory=PaperSection)
    strategy: StrategyCfg = Field(default_factory=StrategyCfg)
    listener: ListenerCfg = Field(default_factory=ListenerCfg)
    notifier: NotifierCfg = Field(default_factory=NotifierCfg)
    api: ApiCfg = Field(default_factory=ApiCfg)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config_file(path: Path | None = None) -> dict[str, Any]:
    target = path or CONFIG_PATH
    if not target.exists():
        return {}
    with target.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data if isinstance(data, dict) else {}


DEFAULT_CONFIG_DICT = AppConfig().model_dump()


def build_config(overrides: dict[str, Any] | None = None) -> AppConfig:
    merged = deep_merge(DEFAULT_CONFIG_DICT, load_config_file())
    if overrides:
        merged = deep_merge(merged, overrides)
    return AppConfig.model_validate(merged)


CONSERVATIVE: dict[str, Any] = {
    "strategy": {
        "min_score_buy": 82,
        "min_score_watch": 65,
        "safety_weight": 0.65,
        "opportunity_weight": 0.35,
        "hard_reject": {"top10_max_pct": 0.40, "top1_max_pct": 0.15, "min_liquidity_usd": 12000, "min_holders": 50},
        "sizing": {"base_pct_of_equity": 0.025, "kelly_fraction": 0.20},
        "exits": {
            "stop_loss_pct": -0.15,
            "trailing_stop_pct": 0.22,
            "take_profits": [
                {"gain_pct": 0.5, "sell_fraction": 0.5},
                {"gain_pct": 1.5, "sell_fraction": 0.5},
            ],
        },
        "circuit_breaker": {"daily_loss_limit_pct": 0.08},
    },
    "paper": {"max_position_pct": 0.06, "max_open_exposure_pct": 0.35, "failed_tx_rate": 0.15},
}

BALANCED: dict[str, Any] = {
    "strategy": {
        "min_score_buy": 55,
        "min_score_watch": 45,
        "safety_weight": 0.55,
        "opportunity_weight": 0.45,
        "hard_reject": {"top10_max_pct": 0.50, "top1_max_pct": 0.22, "min_liquidity_usd": 3000, "min_holders": 25},
        "sizing": {"base_pct_of_equity": 0.05, "kelly_fraction": 0.30},
        "exits": {
            "stop_loss_pct": -0.25,
            "trailing_stop_pct": 0.30,
            "take_profits": [
                {"gain_pct": 1.0, "sell_fraction": 0.5},
                {"gain_pct": 3.0, "sell_fraction": 0.5},
            ],
        },
        "circuit_breaker": {"daily_loss_limit_pct": 0.15},
    },
    "paper": {"max_position_pct": 0.05, "max_open_exposure_pct": 0.60, "max_open_positions": 6, "failed_tx_rate": 0.12},
}

DEGEN: dict[str, Any] = {
    "strategy": {
        "min_score_buy": 64,
        "min_score_watch": 48,
        "safety_weight": 0.45,
        "opportunity_weight": 0.55,
        "hard_reject": {"top10_max_pct": 0.65, "top1_max_pct": 0.30, "min_liquidity_usd": 5000, "min_holders": 12},
        "sizing": {"base_pct_of_equity": 0.06, "kelly_fraction": 0.45},
        "exits": {
            "stop_loss_pct": -0.35,
            "trailing_stop_pct": 0.40,
            "take_profits": [
                {"gain_pct": 1.5, "sell_fraction": 0.4},
                {"gain_pct": 5.0, "sell_fraction": 0.3},
            ],
        },
        "circuit_breaker": {"daily_loss_limit_pct": 0.25},
    },
    "paper": {"max_position_pct": 0.15, "max_open_exposure_pct": 0.80, "failed_tx_rate": 0.10},
}

PRESETS: dict[str, dict[str, Any]] = {
    "conservative": CONSERVATIVE,
    "balanced": BALANCED,
    "degen": DEGEN,
}

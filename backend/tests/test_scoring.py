from app.analyzer.scoring import score_token
from app.config import StrategyCfg, build_config

CLEAN_HARD = {
    "mint_authority_revoked": True,
    "freeze_authority_revoked": True,
    "honeypot": False,
    "top10_pct": 18.0,
    "top1_pct": 5.0,
    "liquidity_usd": 60_000.0,
    "holders": 420,
    "creator_rugs": 0,
}

CHECK_IDS = [
    "mint_authority",
    "freeze_authority",
    "liquidity",
    "lp_lock",
    "holders",
    "creator",
    "bundle",
    "honeypot",
    "rugcheck",
    "metadata",
]

METRIC_IDS = ["momentum", "volume", "buyers", "buy_pressure", "mcap_liquidity"]


def _checks(score: float = 1.0) -> dict:
    checks = {}
    for check_id in CHECK_IDS:
        checks[check_id] = {
            "id": check_id,
            "name": check_id,
            "score": score,
            "passed": score >= 0.5,
            "critical": check_id in ("mint_authority", "freeze_authority", "honeypot"),
            "value": "",
            "detail": "",
            "data": {
                "authority": "creator" if score < 0.5 and "authority" in check_id else None,
                "detected": check_id == "honeypot" and score < 0.5,
                "can_sell": check_id == "honeypot" and score >= 0.5,
                "top10_pct": 18.0,
                "top1_pct": 5.0,
                "count": 420,
                "previous_rugs": 0,
                "tokens_launched": 2,
                "holds_pct": 1.0,
                "usd": 60_000.0,
                "burned": True,
                "locked_days": 0,
                "cluster_pct": 2.0,
                "sniper_wallets": 0,
                "available": True,
                "risks": [],
                "social_count": 3,
                "socials": ["website", "twitter", "telegram"],
                "duplicate_image": False,
                "copycat": False,
            },
        }
    return checks


def _metrics(score: float = 1.0, wash: float = 0.0) -> dict:
    metrics = {}
    for metric_id in METRIC_IDS:
        metrics[metric_id] = {
            "id": metric_id,
            "name": metric_id,
            "score": score,
            "value": "",
            "detail": "",
            "data": {},
        }
    metrics["wash"] = {"id": "wash", "name": "wash", "score": wash, "value": "", "detail": "", "data": {}}
    return metrics


def test_strong_token_is_buy():
    result = score_token(_checks(1.0), _metrics(1.0), StrategyCfg(), CLEAN_HARD)
    assert result.verdict == "BUY"
    assert not result.hard_rejected
    assert abs(result.safety_score - 100.0) < 1e-6
    assert abs(result.opportunity_score - 100.0) < 1e-6
    assert abs(result.final_score - 100.0) < 1e-6
    assert result.green_flags


def test_weak_token_is_avoid():
    hard = dict(CLEAN_HARD, top10_pct=70.0, liquidity_usd=1_000.0, holders=5)
    result = score_token(_checks(0.2), _metrics(0.1), StrategyCfg(), hard)
    assert result.verdict == "AVOID"
    assert result.hard_rejected
    assert len(result.reject_reasons) >= 3


def test_mint_authority_hard_reject():
    result = score_token(_checks(1.0), _metrics(1.0), StrategyCfg(), dict(CLEAN_HARD, mint_authority_revoked=False))
    assert result.hard_rejected
    assert any("Mint authority" in reason for reason in result.reject_reasons)


def test_honeypot_hard_reject():
    result = score_token(_checks(1.0), _metrics(1.0), StrategyCfg(), dict(CLEAN_HARD, honeypot=True))
    assert result.hard_rejected
    assert result.verdict == "AVOID"


def test_unverified_authority_is_rejected():
    result = score_token(_checks(1.0), _metrics(1.0), StrategyCfg(), dict(CLEAN_HARD, mint_authority_revoked=None))
    assert result.hard_rejected


def test_wash_penalty_reduces_opportunity():
    clean = score_token(_checks(1.0), _metrics(1.0, wash=0.0), StrategyCfg(), CLEAN_HARD)
    washed = score_token(_checks(1.0), _metrics(1.0, wash=1.0), StrategyCfg(), CLEAN_HARD)
    assert washed.opportunity_score == clean.opportunity_score - 12.0
    assert washed.final_score < clean.final_score


def test_watch_threshold():
    result = score_token(_checks(0.72), _metrics(0.65), StrategyCfg(), CLEAN_HARD)
    assert result.verdict in ("WATCH", "BUY")
    assert result.final_score >= StrategyCfg().min_score_watch


def test_breakdown_contains_contributions_and_thresholds():
    result = score_token(_checks(1.0), _metrics(1.0), StrategyCfg(), CLEAN_HARD)
    breakdown = result.breakdown
    assert set(breakdown["safety_contributions"]) == set(CHECK_IDS)
    assert "wash_penalty" not in breakdown["opportunity_contributions"]
    assert breakdown["thresholds"]["buy"] == StrategyCfg().min_score_buy


def test_config_from_yaml_matches_defaults():
    config = build_config()
    assert config.strategy.min_score_buy == 74.0
    assert config.paper.starting_balance == 100.0
    assert config.app.mode in ("demo", "live")

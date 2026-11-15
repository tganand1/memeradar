from app.config import PaperSection, StrategyCfg
from app.strategy.sizing import compute_position_size, streak_multiplier


def _size(**overrides):
    kwargs = dict(
        equity=100.0,
        cash=100.0,
        open_value=0.0,
        liquidity_usd=100_000.0,
        score=90.0,
        safety=90.0,
        opportunity=90.0,
        streak_mult=1.0,
        config=StrategyCfg(),
        paper=PaperSection(),
    )
    kwargs.update(overrides)
    return compute_position_size(**kwargs)


def test_size_positive_and_respects_max_position():
    result = _size()
    assert not result.skipped
    assert 1.0 <= result.usd <= 100.0 * PaperSection().max_position_pct
    assert result.reasons and result.caps


def test_higher_score_increases_size():
    low = _size(score=76.0)
    high = _size(score=98.0)
    assert high.usd > low.usd


def test_tighter_pool_cap_limits_size():
    shallow = _size(liquidity_usd=100.0)
    assert shallow.usd <= 100.0 * PaperSection().max_pool_share_pct + 1e-9


def test_cash_reserve_blocks_trade():
    result = _size(cash=10.0)
    assert result.skipped
    assert result.usd == 0.0
    assert result.skip_reason


def test_small_account_is_skipped_below_min_trade():
    result = _size(equity=5.0, cash=5.0, streak_mult=0.45, score=74.0, safety=60.0, opportunity=60.0)
    assert result.usd < PaperSection().min_trade_usd
    assert result.skipped


def test_exposure_cap_limits_new_position():
    result = _size(open_value=59.0, cash=41.0)
    assert result.usd <= 1.0 + 1e-9


def test_streak_multiplier_bounds():
    cfg = StrategyCfg()
    assert streak_multiplier(0, 0, cfg) == 1.0
    assert streak_multiplier(20, 0, cfg) <= cfg.sizing.max_streak_mult
    assert streak_multiplier(0, 20, cfg) >= cfg.sizing.min_streak_mult
    assert streak_multiplier(2, 0, cfg) > 1.0
    assert streak_multiplier(0, 1, cfg) < 1.0

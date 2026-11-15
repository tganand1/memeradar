from app.paper_engine.slippage import amm_slippage, execution_price, execution_slippage, fee_usd


def test_amm_slippage_zero_for_zero_size():
    assert amm_slippage(0, 50_000) == 0.0


def test_amm_slippage_matches_constant_product_formula():
    size = 500.0
    liquidity = 20_000.0
    x = size / (liquidity / 2)
    expected = (1 + x) ** 2 - 1
    assert abs(amm_slippage(size, liquidity) - expected) < 1e-9


def test_amm_slippage_increases_with_size():
    liquidity = 50_000.0
    small = amm_slippage(100.0, liquidity)
    medium = amm_slippage(1_000.0, liquidity)
    large = amm_slippage(10_000.0, liquidity)
    assert 0 < small < medium < large


def test_amm_slippage_capped_for_illiquid_pools():
    assert amm_slippage(1_000_000.0, 100.0) <= 0.95


def test_execution_price_buy_above_and_sell_below_market():
    assert execution_price(1.0, 0.05, "buy") > 1.0
    assert execution_price(1.0, 0.05, "sell") < 1.0


class _FakePaper:
    taker_fee_pct = 0.006
    priority_fee_sol = 0.0008
    jito_tip_sol = 0.0012
    random_slippage_min_pct = 0.01
    random_slippage_max_pct = 0.05


def test_execution_slippage_includes_random_component():
    size = 100.0
    liquidity = 100_000.0
    impact = amm_slippage(size, liquidity)
    import random

    for seed in range(20):
        value = execution_slippage(size, liquidity, random.Random(seed), _FakePaper())
        assert impact + 0.01 - 1e-12 <= value <= impact + 0.05 + 1e-12


def test_fee_includes_taker_and_sol_network_fees():
    fee = fee_usd(1_000.0, _FakePaper(), 200.0)
    expected = 1_000.0 * 0.006 + (0.0008 + 0.0012) * 200.0
    assert abs(fee - expected) < 1e-9

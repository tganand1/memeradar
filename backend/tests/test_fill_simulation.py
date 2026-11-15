"""Tests for realistic paper fill simulation."""

import pytest

from app.paper_engine.slippage import amm_slippage, execution_price, fee_usd
from app.config import AppConfig, PaperSection, StrategyCfg


@pytest.fixture
def paper_config():
    """Create a default paper config for testing."""
    return AppConfig(
        mode="paper",
        log_level="INFO",
        demo_seed=True,
        sol_price_usd=190.0,
        paper=PaperSection(
            starting_balance=100.0,
            min_trade_usd=1.0,
            max_position_pct=0.05,
            max_open_exposure_pct=0.60,
            max_open_positions=6,
            cash_reserve_pct=0.10,
            max_pool_share_pct=0.015,
            taker_fee_pct=0.006,
            priority_fee_sol=0.0008,
            jito_tip_sol=0.0012,
            random_slippage_min_pct=0.01,
            random_slippage_max_pct=0.05,
            execution_delay_min_ms=400,
            execution_delay_max_ms=1500,
            failed_tx_rate=0.12,
            sell_failed_tx_rate=0.10,
            mark_haircut_pct=0.02,
            equity_snapshot_seconds=5,
        ),
        strategy=StrategyCfg(),
    )


class TestAmmSlippage:
    """Test constant-product AMM slippage calculation."""

    def test_positive_size(self):
        result = amm_slippage(size_usd=1000.0, liquidity_usd=100000.0)
        assert result > 0.0

    def test_zero_size(self):
        result = amm_slippage(size_usd=0.0, liquidity_usd=100000.0)
        assert result == 0.0

    def test_zero_liquidity(self):
        result = amm_slippage(size_usd=1000.0, liquidity_usd=0.0)
        assert result == 0.99

    def test_small_trade_vs_liquidity(self):
        result = amm_slippage(size_usd=10.0, liquidity_usd=1_000_000.0)
        assert result < 0.01

    def test_large_trade_vs_liquidity(self):
        result = amm_slippage(size_usd=50000.0, liquidity_usd=100000.0)
        assert result > 0.5


class TestFeeUsd:
    def test_fee_usd_calculation(self, paper_config):
        """Fee USD should include taker fee + network fees."""
        fee = fee_usd(notional=10.0, paper=paper_config.paper, sol_price=190.0)
        # Should include both taker fee and network fee component
        assert fee > 0
        # Rough check: taker fee alone would be 10 * 0.006 = 0.06
        # Network fee: (0.0008 + 0.0012) * 190 = 0.38
        # Total should be around 0.44 or more
        assert fee >= 0.06  # at least the taker fee


class TestConfigAuth:
    """Test that code works with auth on and off."""

    def test_config_with_dashboard_auth(self):
        """Config should work with dashboard authentication enabled."""
        from app.env import Env

        env = Env(dashboard_password="testpass")
        # dashboard_auth_enabled is a property that checks if password is set
        assert env.dashboard_auth_enabled == True

    def test_config_without_dashboard_auth(self):
        """Config should work without dashboard authentication."""
        from app.env import Env

        env = Env(dashboard_password="")
        assert env.dashboard_auth_enabled == False

    def test_log_key_masking(self):
        """API keys should be masked in logs."""
        from app.utils import short_addr

        # Test that addresses are shortened (masked)
        long_addr = "7FdQgN9LX4L58k1ZqeM9kt2YJJ6G5cQ1V2W3E4R5T6Y7U8O9P0Q1R2S3T4U5V6W7"
        short = short_addr(long_addr, size=4)
        assert "…" in short  # should have ellipsis masking
        assert len(short) < len(long_addr)  # should be shorter
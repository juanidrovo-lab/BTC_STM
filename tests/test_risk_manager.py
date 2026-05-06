import pytest

from btc_stm.risk import RiskManager
from btc_stm.settings import Settings


def test_order_validation_passes_with_safe_notional() -> None:
    manager = RiskManager(max_order_notional=1_000)
    manager.validate_order(quantity=0.01, price=50_000)


def test_order_validation_rejects_large_notional() -> None:
    manager = RiskManager(max_order_notional=1_000)
    with pytest.raises(ValueError, match="exceeds max allowed"):
        manager.validate_order(quantity=0.1, price=20_000)


def test_live_guard_rejects_live_without_opt_in() -> None:
    manager = RiskManager()
    settings = Settings(
        TRADING_MODE="live",
        ENABLE_LIVE_TRADING=True,
        LIVE_TRADING_OPT_IN=False,
    )
    with pytest.raises(ValueError, match="Live trading is blocked"):
        manager.enforce_live_trading_guard(settings)

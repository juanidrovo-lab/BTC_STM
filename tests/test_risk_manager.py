from decimal import Decimal

import pytest

from btc_stm.domain import BinanceSymbolFilters
from btc_stm.risk import RiskManager
from btc_stm.settings import Settings


def _filters() -> BinanceSymbolFilters:
    return BinanceSymbolFilters(
        min_qty=Decimal("0.001"),
        max_qty=Decimal("100"),
        step_size=Decimal("0.001"),
        min_price=Decimal("0.01"),
        max_price=Decimal("1000000"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal("10"),
    )


def test_order_validation_passes_with_binance_filters() -> None:
    manager = RiskManager(max_order_notional=Decimal("1000"))
    manager.validate_order(
        quantity=Decimal("0.010"),
        price=Decimal("50000.00"),
        filters=_filters(),
    )


def test_order_validation_rejects_bad_step_size() -> None:
    manager = RiskManager(max_order_notional=Decimal("1000"))
    with pytest.raises(ValueError, match="step size"):
        manager.validate_order(
            quantity=Decimal("0.0105"),
            price=Decimal("50000.00"),
            filters=_filters(),
        )


def test_order_validation_rejects_bad_tick_size() -> None:
    manager = RiskManager(max_order_notional=Decimal("1000"))
    with pytest.raises(ValueError, match="tick size"):
        manager.validate_order(
            quantity=Decimal("0.010"),
            price=Decimal("50000.005"),
            filters=_filters(),
        )


def test_order_validation_rejects_large_notional() -> None:
    manager = RiskManager(max_order_notional=Decimal("1000"))
    with pytest.raises(ValueError, match="exceeds max allowed"):
        manager.validate_order(
            quantity=Decimal("0.100"),
            price=Decimal("20000.00"),
            filters=_filters(),
        )


def test_live_guard_rejects_live_without_opt_in() -> None:
    manager = RiskManager()
    settings = Settings(
        TRADING_MODE="live",
        ENABLE_LIVE_TRADING=True,
        LIVE_TRADING_OPT_IN=False,
    )
    with pytest.raises(ValueError, match="Live trading is blocked"):
        manager.enforce_live_trading_guard(settings)

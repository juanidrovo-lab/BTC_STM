from decimal import Decimal

import pytest
from pydantic import ValidationError

from btc_stm.domain import OrderIntent, OrderSide, OrderType, PortfolioState, SymbolFilters
from btc_stm.risk import RiskManager
from btc_stm.settings import Settings


def make_filters() -> SymbolFilters:
    return SymbolFilters(
        symbol="BTCUSDT",
        price_min=Decimal("10"),
        price_max=Decimal("1000000"),
        price_tick_size=Decimal("0.1"),
        qty_min=Decimal("0.001"),
        qty_max=Decimal("100"),
        qty_step_size=Decimal("0.001"),
        min_notional=Decimal("5"),
    )


def make_portfolio() -> PortfolioState:
    return PortfolioState(equity=Decimal("1000"), daily_pnl=Decimal("0"), open_positions=0)


def test_reject_order_without_stop_loss() -> None:
    risk = RiskManager(Settings())
    decision = risk.evaluate(
        order=OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.01"),
            price=Decimal("50000.0"),
            stop_loss=None,
        ),
        portfolio=make_portfolio(),
        filters=make_filters(),
    )
    assert decision.approved is False
    assert any("stop-loss" in reason for reason in decision.reasons)


def test_accept_valid_order() -> None:
    risk = RiskManager(Settings())
    decision = risk.evaluate(
        order=OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.002"),
            price=Decimal("50000.0"),
            stop_loss=Decimal("49800.0"),
        ),
        portfolio=make_portfolio(),
        filters=make_filters(),
    )
    assert decision.approved is True


def test_reject_kill_switch_and_limits() -> None:
    settings = Settings(risk_kill_switch=True, risk_max_open_positions=1)
    risk = RiskManager(settings)
    portfolio = PortfolioState(equity=Decimal("1000"), daily_pnl=Decimal("-60"), open_positions=1)
    decision = risk.evaluate(
        order=OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.5"),
            price=Decimal("1000.0"),
            stop_loss=Decimal("900.0"),
        ),
        portfolio=portfolio,
        filters=make_filters(),
    )
    assert decision.approved is False
    assert len(decision.reasons) >= 3


def test_reject_exchange_filter_violations() -> None:
    risk = RiskManager(Settings())
    decision = risk.evaluate(
        order=OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.0015"),
            price=Decimal("10.05"),
            stop_loss=Decimal("9.9"),
        ),
        portfolio=make_portfolio(),
        filters=make_filters(),
    )
    assert decision.approved is False
    assert any("PRICE_FILTER" in reason for reason in decision.reasons)
    assert any("LOT_SIZE" in reason for reason in decision.reasons)


def make_offset_filters(min_notional: Decimal = Decimal("5")) -> SymbolFilters:
    return SymbolFilters(
        symbol="BTCUSDT",
        price_min=Decimal("0.03"),
        price_max=Decimal("1000000"),
        price_tick_size=Decimal("0.02"),
        qty_min=Decimal("0.015"),
        qty_max=Decimal("100"),
        qty_step_size=Decimal("0.01"),
        min_notional=min_notional,
    )


def test_price_filter_allows_min_price_not_exact_tick_multiple() -> None:
    risk = RiskManager(Settings())
    decision = risk.evaluate(
        order=OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("5.005"),
            price=Decimal("0.03"),
            stop_loss=Decimal("0.02"),
        ),
        portfolio=make_portfolio(),
        filters=make_offset_filters(min_notional=Decimal("0.0001")),
    )

    assert not any("PRICE_FILTER" in reason for reason in decision.reasons)


def test_price_filter_uses_min_price_offset_valid_case() -> None:
    risk = RiskManager(Settings())
    decision = risk.evaluate(
        order=OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("5.005"),
            price=Decimal("1.03"),
            stop_loss=Decimal("0.93"),
        ),
        portfolio=make_portfolio(),
        filters=make_offset_filters(),
    )

    assert decision.approved is True


def test_price_filter_uses_min_price_offset_invalid_case() -> None:
    risk = RiskManager(Settings())
    decision = risk.evaluate(
        order=OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("5.005"),
            price=Decimal("1.04"),
            stop_loss=Decimal("0.93"),
        ),
        portfolio=make_portfolio(),
        filters=make_offset_filters(),
    )

    assert decision.approved is False
    assert any("PRICE_FILTER" in reason for reason in decision.reasons)


def test_lot_size_allows_min_qty_not_exact_step_multiple() -> None:
    risk = RiskManager(Settings())
    decision = risk.evaluate(
        order=OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.015"),
            price=Decimal("500"),
            stop_loss=Decimal("490"),
        ),
        portfolio=make_portfolio(),
        filters=make_offset_filters(),
    )

    assert not any("LOT_SIZE" in reason for reason in decision.reasons)


def test_lot_size_uses_min_qty_offset_valid_case() -> None:
    risk = RiskManager(Settings())
    decision = risk.evaluate(
        order=OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("5.005"),
            price=Decimal("1.03"),
            stop_loss=Decimal("0.93"),
        ),
        portfolio=make_portfolio(),
        filters=make_offset_filters(),
    )

    assert decision.approved is True


def test_lot_size_uses_min_qty_offset_invalid_case() -> None:
    risk = RiskManager(Settings())
    decision = risk.evaluate(
        order=OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("5.001"),
            price=Decimal("1.03"),
            stop_loss=Decimal("0.93"),
        ),
        portfolio=make_portfolio(),
        filters=make_offset_filters(),
    )

    assert decision.approved is False
    assert any("LOT_SIZE" in reason for reason in decision.reasons)


def test_rejects_non_finite_order_price() -> None:
    with pytest.raises(ValidationError, match="finite number"):
        OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.002"),
            price=Decimal("NaN"),
            stop_loss=Decimal("49800.0"),
        )


def test_rejects_non_finite_order_quantity() -> None:
    with pytest.raises(ValidationError, match="finite number"):
        OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("Infinity"),
            price=Decimal("50000.0"),
            stop_loss=Decimal("49800.0"),
        )


def test_rejects_non_finite_stop_loss() -> None:
    with pytest.raises(ValidationError, match="finite number"):
        OrderIntent(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.002"),
            price=Decimal("50000.0"),
            stop_loss=Decimal("-Infinity"),
        )

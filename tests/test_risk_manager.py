from decimal import Decimal

from btc_stm.models import OrderIntent, OrderSide, OrderType, SymbolFilters
from btc_stm.risk import RiskManager


def _filters() -> SymbolFilters:
    return SymbolFilters(
        min_price=Decimal("0.03"),
        max_price=Decimal("1000000"),
        tick_size=Decimal("0.02"),
        min_qty=Decimal("0.015"),
        max_qty=Decimal("100"),
        step_size=Decimal("0.01"),
        min_notional=Decimal("5"),
    )


def _intent(price: str, quantity: str, stop_loss_price: str | None = None) -> OrderIntent:
    return OrderIntent(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal(price),
        quantity=Decimal(quantity),
        stop_loss_price=Decimal(stop_loss_price) if stop_loss_price else None,
    )


def test_price_filter_uses_min_price_offset_valid_case() -> None:
    decision = RiskManager().evaluate(_intent("1.03", "5.005"), _filters())
    assert decision.approved


def test_price_filter_uses_min_price_offset_invalid_case() -> None:
    decision = RiskManager().evaluate(_intent("1.04", "5.005"), _filters())
    assert not decision.approved
    assert "PRICE_FILTER" in (decision.reason or "")


def test_lot_size_uses_min_qty_offset_valid_case() -> None:
    decision = RiskManager().evaluate(_intent("1.03", "5.005"), _filters())
    assert decision.approved


def test_lot_size_uses_min_qty_offset_invalid_case() -> None:
    decision = RiskManager().evaluate(_intent("1.03", "5.001"), _filters())
    assert not decision.approved
    assert "LOT_SIZE" in (decision.reason or "")


def test_rejects_non_finite_values() -> None:
    manager = RiskManager()
    finite_filters = _filters()

    assert not manager.evaluate(_intent("NaN", "5"), finite_filters).approved
    assert not manager.evaluate(_intent("Infinity", "5"), finite_filters).approved
    assert not manager.evaluate(_intent("1.03", "-Infinity"), finite_filters).approved
    assert not manager.evaluate(_intent("1.03", "5", "NaN"), finite_filters).approved

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from btc_stm.domain import OrderSide
from btc_stm.execution.fees import calculate_fee
from btc_stm.execution.models import ExecutionStatus, Fill, PaperPortfolio, PaperPosition
from btc_stm.execution.slippage import apply_slippage


def test_calculate_fee_calculates_basis_points() -> None:
    assert calculate_fee(Decimal("1000"), Decimal("10")) == Decimal("1")


def test_calculate_fee_rejects_negative_inputs() -> None:
    with pytest.raises(ValueError, match="notional"):
        calculate_fee(Decimal("-1"), Decimal("10"))
    with pytest.raises(ValueError, match="fee_rate_bps"):
        calculate_fee(Decimal("100"), Decimal("-1"))


def test_calculate_fee_rejects_non_finite_inputs() -> None:
    with pytest.raises(ValueError, match="notional"):
        calculate_fee(Decimal("NaN"), Decimal("10"))
    with pytest.raises(ValueError, match="notional"):
        calculate_fee(Decimal("Infinity"), Decimal("10"))
    with pytest.raises(ValueError, match="fee_rate_bps"):
        calculate_fee(Decimal("100"), Decimal("-Infinity"))


def test_apply_slippage_increases_price_for_buy() -> None:
    assert apply_slippage(Decimal("100"), OrderSide.BUY, Decimal("25")) == Decimal("100.25")


def test_apply_slippage_reduces_price_for_sell() -> None:
    assert apply_slippage(Decimal("100"), OrderSide.SELL, Decimal("25")) == Decimal("99.75")


def test_apply_slippage_rejects_non_finite_inputs() -> None:
    with pytest.raises(ValueError, match="price"):
        apply_slippage(Decimal("NaN"), OrderSide.BUY, Decimal("10"))
    with pytest.raises(ValueError, match="price"):
        apply_slippage(Decimal("Infinity"), OrderSide.BUY, Decimal("10"))
    with pytest.raises(ValueError, match="slippage_bps"):
        apply_slippage(Decimal("100"), OrderSide.BUY, Decimal("-Infinity"))


def test_apply_slippage_rejects_non_positive_sell_result() -> None:
    with pytest.raises(ValueError, match="non-positive final price"):
        apply_slippage(Decimal("100"), OrderSide.SELL, Decimal("10000"))


def test_fill_rejects_non_positive_price_and_quantity() -> None:
    with pytest.raises(ValidationError):
        Fill(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            price=Decimal("0"),
            quantity=Decimal("1"),
            fee=Decimal("0"),
            fee_asset="USDT",
            executed_at=datetime(2026, 5, 6, tzinfo=UTC),
        )


def test_paper_portfolio_defaults_positions() -> None:
    portfolio = PaperPortfolio(cash_balance=Decimal("1000"))

    assert portfolio.positions == {}
    assert portfolio.realized_pnl == Decimal("0")
    assert portfolio.total_fees_paid == Decimal("0")


def test_execution_status_values() -> None:
    assert ExecutionStatus.ACCEPTED.value == "accepted"
    assert ExecutionStatus.REJECTED.value == "rejected"
    assert ExecutionStatus.FILLED.value == "filled"
    assert ExecutionStatus.PARTIALLY_FILLED.value == "partially_filled"


def test_paper_position_normalizes_symbol() -> None:
    position = PaperPosition(
        symbol="btcusdt",
        quantity=Decimal("1"),
        average_entry_price=Decimal("50000"),
    )

    assert position.symbol == "BTCUSDT"

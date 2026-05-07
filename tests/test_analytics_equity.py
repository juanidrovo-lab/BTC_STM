from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from btc_stm.analytics.equity import (
    analyze_equity_curve,
    calculate_drawdown_points,
    calculate_return_points,
    validate_equity_curve,
)
from btc_stm.backtesting.models import EquityPoint


def make_equity_point(
    timestamp: datetime,
    equity: Decimal,
    *,
    cash_balance: Decimal | None = None,
    position_value: Decimal = Decimal("0"),
) -> EquityPoint:
    return EquityPoint(
        timestamp=timestamp,
        equity=equity,
        cash_balance=cash_balance if cash_balance is not None else equity,
        position_value=position_value,
        realized_pnl=Decimal("0"),
    )


def test_validate_equity_curve_rejects_empty_curve() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        validate_equity_curve([])


def test_validate_equity_curve_rejects_duplicate_timestamps() -> None:
    timestamp = datetime(2026, 5, 7, tzinfo=UTC)

    with pytest.raises(ValueError, match="duplicate"):
        validate_equity_curve(
            [
                make_equity_point(timestamp, Decimal("100")),
                make_equity_point(timestamp, Decimal("101")),
            ]
        )


def test_validate_equity_curve_rejects_out_of_order_curve() -> None:
    timestamp = datetime(2026, 5, 7, tzinfo=UTC)

    with pytest.raises(ValueError, match="chronological"):
        validate_equity_curve(
            [
                make_equity_point(timestamp + timedelta(minutes=1), Decimal("101")),
                make_equity_point(timestamp, Decimal("100")),
            ]
        )


def test_validate_equity_curve_rejects_non_finite_equity() -> None:
    timestamp = datetime(2026, 5, 7, tzinfo=UTC)
    point = EquityPoint.model_construct(
        timestamp=timestamp,
        equity=Decimal("NaN"),
        cash_balance=Decimal("100"),
        position_value=Decimal("0"),
        realized_pnl=Decimal("0"),
    )

    with pytest.raises(ValueError, match="equity"):
        validate_equity_curve([point])


def test_validate_equity_curve_rejects_negative_equity() -> None:
    timestamp = datetime(2026, 5, 7, tzinfo=UTC)
    point = EquityPoint.model_construct(
        timestamp=timestamp,
        equity=Decimal("-1"),
        cash_balance=Decimal("0"),
        position_value=Decimal("0"),
        realized_pnl=Decimal("0"),
    )

    with pytest.raises(ValueError, match="Equity"):
        validate_equity_curve([point])


def test_calculate_return_points_calculates_period_returns() -> None:
    timestamp = datetime(2026, 5, 7, tzinfo=UTC)
    points = [
        make_equity_point(timestamp, Decimal("100")),
        make_equity_point(timestamp + timedelta(minutes=1), Decimal("110")),
        make_equity_point(timestamp + timedelta(minutes=2), Decimal("99")),
    ]

    returns = calculate_return_points(points)

    assert [point.period_return_pct for point in returns] == [
        Decimal("0"),
        Decimal("10.0"),
        Decimal("-10.0"),
    ]


def test_calculate_return_points_handles_previous_zero_equity() -> None:
    timestamp = datetime(2026, 5, 7, tzinfo=UTC)
    points = [
        make_equity_point(timestamp, Decimal("0")),
        make_equity_point(timestamp + timedelta(minutes=1), Decimal("100")),
    ]

    returns = calculate_return_points(points)

    assert [point.period_return_pct for point in returns] == [
        Decimal("0"),
        Decimal("0"),
    ]


def test_calculate_drawdown_points_uses_historical_peak() -> None:
    timestamp = datetime(2026, 5, 7, tzinfo=UTC)
    points = [
        make_equity_point(timestamp, Decimal("100")),
        make_equity_point(timestamp + timedelta(minutes=1), Decimal("120")),
        make_equity_point(timestamp + timedelta(minutes=2), Decimal("90")),
    ]

    drawdowns = calculate_drawdown_points(points)

    assert drawdowns[-1].peak_equity == Decimal("120")
    assert drawdowns[-1].drawdown_pct == Decimal("25.00")


def test_analyze_equity_curve_calculates_return_and_drawdown_bounds() -> None:
    timestamp = datetime(2026, 5, 7, tzinfo=UTC)
    points = [
        make_equity_point(timestamp, Decimal("100")),
        make_equity_point(timestamp + timedelta(minutes=1), Decimal("120")),
        make_equity_point(timestamp + timedelta(minutes=2), Decimal("90")),
        make_equity_point(timestamp + timedelta(minutes=3), Decimal("150")),
    ]

    analysis = analyze_equity_curve(points)

    assert analysis.total_return_pct == Decimal("50.0")
    assert analysis.max_drawdown_pct == Decimal("25.00")
    assert analysis.max_drawdown_start == timestamp + timedelta(minutes=1)
    assert analysis.max_drawdown_end == timestamp + timedelta(minutes=2)

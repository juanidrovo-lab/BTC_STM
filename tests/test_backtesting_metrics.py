from datetime import UTC, datetime, timedelta
from decimal import Decimal

from btc_stm.backtesting.metrics import (
    build_backtest_metrics,
    calculate_max_drawdown_pct,
    calculate_total_return_pct,
)
from btc_stm.backtesting.models import EquityPoint


def make_equity_point(index: int, equity: Decimal) -> EquityPoint:
    return EquityPoint(
        timestamp=datetime(2026, 5, 7, 12, 0, tzinfo=UTC) + timedelta(minutes=index),
        equity=equity,
        cash_balance=equity,
        position_value=Decimal("0"),
        realized_pnl=Decimal("0"),
    )


def test_calculate_total_return_pct() -> None:
    assert calculate_total_return_pct(Decimal("100"), Decimal("125")) == Decimal("25.00")


def test_calculate_max_drawdown_pct() -> None:
    equity_curve = [
        make_equity_point(0, Decimal("100")),
        make_equity_point(1, Decimal("80")),
        make_equity_point(2, Decimal("120")),
        make_equity_point(3, Decimal("90")),
    ]

    assert calculate_max_drawdown_pct(equity_curve) == Decimal("25.00")


def test_build_backtest_metrics() -> None:
    equity_curve = [make_equity_point(0, Decimal("100")), make_equity_point(1, Decimal("110"))]

    metrics = build_backtest_metrics(
        starting_equity=Decimal("100"),
        ending_equity=Decimal("110"),
        equity_curve=equity_curve,
        trades=[],
        total_fees_paid=Decimal("1"),
    )

    assert metrics.total_return_pct == Decimal("10.0")
    assert metrics.max_drawdown_pct == Decimal("0")
    assert metrics.total_trades == 0
    assert metrics.total_fees_paid == Decimal("1")

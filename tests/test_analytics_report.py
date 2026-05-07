from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from btc_stm.analytics.report import build_performance_report
from btc_stm.backtesting.models import (
    BacktestConfig,
    BacktestMetrics,
    BacktestResult,
    BacktestTrade,
    EquityPoint,
)
from btc_stm.domain import OrderSide
from btc_stm.execution.models import ExecutionReport, ExecutionStatus


def make_equity_point(timestamp: datetime, equity: Decimal) -> EquityPoint:
    return EquityPoint(
        timestamp=timestamp,
        equity=equity,
        cash_balance=equity,
        position_value=Decimal("0"),
        realized_pnl=Decimal("0"),
    )


def make_report(
    status: ExecutionStatus,
    *,
    notional: Decimal = Decimal("100"),
    total_fee: Decimal = Decimal("1"),
    filled_quantity: Decimal = Decimal("1"),
    average_fill_price: Decimal = Decimal("100"),
) -> ExecutionReport:
    return ExecutionReport(
        client_order_id=f"order-{status.value}",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        status=status,
        requested_price=Decimal("100"),
        requested_quantity=Decimal("1"),
        filled_quantity=filled_quantity,
        average_fill_price=average_fill_price,
        notional=notional,
        total_fee=total_fee,
        reason="risk" if status is ExecutionStatus.REJECTED else None,
        created_at=datetime(2026, 5, 7, tzinfo=UTC),
        fills=[],
    )


def make_backtest_result(
    *,
    equity_values: list[Decimal],
    reports: list[ExecutionReport],
) -> BacktestResult:
    start = datetime(2026, 5, 7, tzinfo=UTC)
    equity_curve = [
        make_equity_point(start + timedelta(minutes=index), equity)
        for index, equity in enumerate(equity_values)
    ]
    trades = [
        BacktestTrade(timestamp=start + timedelta(minutes=index), execution_report=report)
        for index, report in enumerate(reports)
    ]
    return BacktestResult(
        config=BacktestConfig(
            symbol="BTCUSDT",
            initial_cash=equity_values[0],
            fee_rate_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
        ),
        trades=trades,
        equity_curve=equity_curve,
        metrics=BacktestMetrics(
            starting_equity=equity_values[0],
            ending_equity=equity_values[-1],
            total_return_pct=Decimal("0"),
            max_drawdown_pct=Decimal("0"),
            total_trades=len(trades),
            winning_trades=0,
            losing_trades=0,
            total_fees_paid=Decimal("0"),
        ),
    )


def test_build_performance_report_works_with_backtest_result() -> None:
    result = make_backtest_result(
        equity_values=[Decimal("100"), Decimal("110")],
        reports=[make_report(ExecutionStatus.FILLED)],
    )

    report = build_performance_report(result)

    assert report.equity.ending_equity == Decimal("110")
    assert report.trades.filled_reports == 1
    assert report.trades.total_notional == Decimal("100")


def test_build_performance_report_warns_when_no_trades() -> None:
    result = make_backtest_result(
        equity_values=[Decimal("100"), Decimal("110")],
        reports=[],
    )

    report = build_performance_report(result)

    assert "Backtest produced no trades." in report.warnings


def test_build_performance_report_warns_for_rejected_reports() -> None:
    rejected = make_report(
        ExecutionStatus.REJECTED,
        notional=Decimal("0"),
        filled_quantity=Decimal("0"),
        average_fill_price=Decimal("0"),
    )
    result = make_backtest_result(
        equity_values=[Decimal("100"), Decimal("110")],
        reports=[rejected],
    )

    report = build_performance_report(result)

    assert "Backtest contains rejected execution reports." in report.warnings


def test_build_performance_report_warns_when_ending_below_starting() -> None:
    result = make_backtest_result(
        equity_values=[Decimal("100"), Decimal("90")],
        reports=[],
    )

    report = build_performance_report(result)

    assert "Ending equity is below starting equity." in report.warnings


def test_build_performance_report_warns_for_large_drawdown() -> None:
    result = make_backtest_result(
        equity_values=[Decimal("100"), Decimal("120"), Decimal("80")],
        reports=[],
    )

    report = build_performance_report(result)

    assert "Max drawdown exceeded 20%." in report.warnings


def test_build_performance_report_warns_for_zero_equity_return_period() -> None:
    result = make_backtest_result(
        equity_values=[Decimal("1"), Decimal("0"), Decimal("10")],
        reports=[],
    )

    report = build_performance_report(result)

    assert "Equity curve contains zero equity; period return set to zero." in report.warnings


def test_analytics_package_has_no_network_or_dangerous_patterns() -> None:
    analytics_dir = Path("src/btc_stm/analytics")
    forbidden = (
        "requests",
        "httpx",
        "aiohttp",
        "websockets",
        "socket",
        "api_key",
        "secret",
        "hmac",
        "private",
        "create_order",
        "cancel_order",
        "place_order",
        "def buy",
        "def sell",
        "predict",
        "sklearn",
        "tensorflow",
        "torch",
        "optimiz",
    )
    scanned = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in analytics_dir.rglob("*.py")
    )

    assert not any(pattern in scanned for pattern in forbidden)

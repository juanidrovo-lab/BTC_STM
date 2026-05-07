from datetime import UTC, datetime
from decimal import Decimal

import pytest

from btc_stm.analytics.trades import analyze_execution_reports
from btc_stm.domain import OrderSide
from btc_stm.execution.models import ExecutionReport, ExecutionStatus


def make_report(
    status: ExecutionStatus,
    *,
    notional: Decimal = Decimal("100"),
    fee: Decimal = Decimal("1"),
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
        total_fee=fee,
        reason="risk" if status is ExecutionStatus.REJECTED else None,
        created_at=datetime(2026, 5, 7, tzinfo=UTC),
        fills=[],
    )


def test_analyze_execution_reports_counts_filled_and_rejected() -> None:
    analytics = analyze_execution_reports(
        [
            make_report(ExecutionStatus.FILLED),
            make_report(
                ExecutionStatus.REJECTED,
                notional=Decimal("0"),
                filled_quantity=Decimal("0"),
                average_fill_price=Decimal("0"),
            ),
        ]
    )

    assert analytics.total_reports == 2
    assert analytics.filled_reports == 1
    assert analytics.rejected_reports == 1


def test_analyze_execution_reports_calculates_total_notional_and_fees() -> None:
    analytics = analyze_execution_reports(
        [
            make_report(
                ExecutionStatus.FILLED,
                notional=Decimal("100"),
                fee=Decimal("1"),
            ),
            make_report(
                ExecutionStatus.PARTIALLY_FILLED,
                notional=Decimal("50"),
                fee=Decimal("0.5"),
                filled_quantity=Decimal("0.5"),
            ),
            make_report(
                ExecutionStatus.REJECTED,
                notional=Decimal("0"),
                fee=Decimal("0.1"),
                filled_quantity=Decimal("0"),
                average_fill_price=Decimal("0"),
            ),
        ]
    )

    assert analytics.total_notional == Decimal("150")
    assert analytics.total_fees == Decimal("1.6")
    assert analytics.partially_filled_reports == 1


def test_analyze_execution_reports_calculates_weighted_average_fill_price() -> None:
    analytics = analyze_execution_reports(
        [
            make_report(
                ExecutionStatus.FILLED,
                filled_quantity=Decimal("1"),
                average_fill_price=Decimal("100"),
            ),
            make_report(
                ExecutionStatus.FILLED,
                filled_quantity=Decimal("3"),
                average_fill_price=Decimal("200"),
            ),
        ]
    )

    assert analytics.average_fill_price == Decimal("175")


def test_analyze_execution_reports_returns_no_average_without_fills() -> None:
    analytics = analyze_execution_reports(
        [
            make_report(
                ExecutionStatus.REJECTED,
                notional=Decimal("0"),
                filled_quantity=Decimal("0"),
                average_fill_price=Decimal("0"),
            )
        ]
    )

    assert analytics.average_fill_price is None


def test_analyze_execution_reports_rejects_non_finite_numbers() -> None:
    report = ExecutionReport.model_construct(
        client_order_id="bad",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        status=ExecutionStatus.FILLED,
        requested_price=Decimal("100"),
        requested_quantity=Decimal("1"),
        filled_quantity=Decimal("1"),
        average_fill_price=Decimal("NaN"),
        notional=Decimal("100"),
        total_fee=Decimal("1"),
        reason=None,
        created_at=datetime(2026, 5, 7, tzinfo=UTC),
        fills=[],
    )

    with pytest.raises(ValueError, match="finite"):
        analyze_execution_reports([report])

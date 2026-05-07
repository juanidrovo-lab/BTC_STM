"""Execution report analytics."""

from __future__ import annotations

from decimal import Decimal

from btc_stm.analytics.models import TradeAnalytics
from btc_stm.execution.models import ExecutionReport, ExecutionStatus


def analyze_execution_reports(reports: list[ExecutionReport]) -> TradeAnalytics:
    filled_reports = 0
    rejected_reports = 0
    partially_filled_reports = 0
    total_notional = Decimal("0")
    total_fees = Decimal("0")
    weighted_fill_price = Decimal("0")
    total_filled_quantity = Decimal("0")

    for report in reports:
        _validate_report_numbers(report)
        if report.status is ExecutionStatus.FILLED:
            filled_reports += 1
            total_notional += report.notional
        elif report.status is ExecutionStatus.REJECTED:
            rejected_reports += 1
        elif report.status is ExecutionStatus.PARTIALLY_FILLED:
            partially_filled_reports += 1
            total_notional += report.notional

        total_fees += report.total_fee
        if report.filled_quantity > 0:
            weighted_fill_price += report.average_fill_price * report.filled_quantity
            total_filled_quantity += report.filled_quantity

    average_fill_price = (
        weighted_fill_price / total_filled_quantity
        if total_filled_quantity > 0
        else None
    )
    return TradeAnalytics(
        total_reports=len(reports),
        filled_reports=filled_reports,
        rejected_reports=rejected_reports,
        partially_filled_reports=partially_filled_reports,
        total_notional=total_notional,
        total_fees=total_fees,
        average_fill_price=average_fill_price,
    )


def _validate_report_numbers(report: ExecutionReport) -> None:
    values = [
        report.notional,
        report.total_fee,
        report.average_fill_price,
        report.filled_quantity,
    ]
    if not all(value.is_finite() for value in values):
        raise ValueError("Execution report numeric values must be finite.")

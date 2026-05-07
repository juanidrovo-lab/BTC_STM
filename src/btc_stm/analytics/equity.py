"""Equity curve analytics."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from btc_stm.analytics.models import DrawdownPoint, EquityCurveAnalysis, ReturnPoint
from btc_stm.backtesting.models import EquityPoint


def validate_equity_curve(equity_curve: list[EquityPoint]) -> None:
    if not equity_curve:
        raise ValueError("Equity curve must not be empty.")

    previous_timestamp: datetime | None = None
    seen_timestamps: set[datetime] = set()
    for point in equity_curve:
        if point.timestamp in seen_timestamps:
            raise ValueError("Equity curve must not contain duplicate timestamps.")
        if previous_timestamp is not None and point.timestamp <= previous_timestamp:
            raise ValueError("Equity curve must be in chronological order.")
        _validate_finite("equity", point.equity)
        _validate_finite("cash_balance", point.cash_balance)
        _validate_finite("position_value", point.position_value)
        if point.equity < 0:
            raise ValueError("Equity must be greater than or equal to zero.")
        if point.cash_balance < 0:
            raise ValueError("Cash balance must be greater than or equal to zero.")
        if point.position_value < 0:
            raise ValueError("Position value must be greater than or equal to zero.")
        seen_timestamps.add(point.timestamp)
        previous_timestamp = point.timestamp


def calculate_return_points(equity_curve: list[EquityPoint]) -> list[ReturnPoint]:
    validate_equity_curve(equity_curve)
    return_points: list[ReturnPoint] = []
    previous_equity: Decimal | None = None
    for point in equity_curve:
        if previous_equity is None or previous_equity == 0:
            period_return_pct = Decimal("0")
        else:
            period_return_pct = (point.equity - previous_equity) / previous_equity * Decimal("100")
        return_points.append(
            ReturnPoint(
                timestamp=point.timestamp,
                equity=point.equity,
                period_return_pct=period_return_pct,
            )
        )
        previous_equity = point.equity
    return return_points


def calculate_drawdown_points(equity_curve: list[EquityPoint]) -> list[DrawdownPoint]:
    validate_equity_curve(equity_curve)
    drawdown_points: list[DrawdownPoint] = []
    peak_equity = equity_curve[0].equity
    for point in equity_curve:
        if point.equity > peak_equity:
            peak_equity = point.equity
        if peak_equity == 0:
            drawdown_pct = Decimal("0")
        else:
            drawdown_pct = (peak_equity - point.equity) / peak_equity * Decimal("100")
        drawdown_points.append(
            DrawdownPoint(
                timestamp=point.timestamp,
                equity=point.equity,
                peak_equity=peak_equity,
                drawdown_pct=drawdown_pct,
            )
        )
    return drawdown_points


def analyze_equity_curve(equity_curve: list[EquityPoint]) -> EquityCurveAnalysis:
    validate_equity_curve(equity_curve)
    starting_equity = equity_curve[0].equity
    ending_equity = equity_curve[-1].equity
    if starting_equity <= 0:
        raise ValueError("starting_equity must be greater than zero.")

    return_points = calculate_return_points(equity_curve)
    drawdown_points = calculate_drawdown_points(equity_curve)
    total_return_pct = (ending_equity - starting_equity) / starting_equity * Decimal("100")

    max_drawdown = max(point.drawdown_pct for point in drawdown_points)
    max_drawdown_point = next(
        point for point in drawdown_points if point.drawdown_pct == max_drawdown
    )
    max_drawdown_start = _find_peak_timestamp(equity_curve, max_drawdown_point.timestamp)
    max_drawdown_end = max_drawdown_point.timestamp if max_drawdown > 0 else None

    return EquityCurveAnalysis(
        starting_equity=starting_equity,
        ending_equity=ending_equity,
        total_return_pct=total_return_pct,
        max_drawdown_pct=max_drawdown,
        max_drawdown_start=max_drawdown_start if max_drawdown > 0 else None,
        max_drawdown_end=max_drawdown_end,
        return_points=return_points,
        drawdown_points=drawdown_points,
    )


def _find_peak_timestamp(equity_curve: list[EquityPoint], until_timestamp: datetime) -> datetime:
    peak_equity = Decimal("0")
    peak_timestamp = equity_curve[0].timestamp
    for point in equity_curve:
        if point.timestamp > until_timestamp:
            break
        if point.equity >= peak_equity:
            peak_equity = point.equity
            peak_timestamp = point.timestamp
    return peak_timestamp


def _validate_finite(name: str, value: Decimal) -> None:
    if not value.is_finite():
        raise ValueError(f"{name} must be finite.")

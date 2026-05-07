"""Backtest performance metrics."""

from __future__ import annotations

from decimal import Decimal

from btc_stm.backtesting.models import BacktestMetrics, BacktestTrade, EquityPoint


def calculate_total_return_pct(starting_equity: Decimal, ending_equity: Decimal) -> Decimal:
    _validate_finite("starting_equity", starting_equity)
    _validate_finite("ending_equity", ending_equity)
    if starting_equity <= 0:
        raise ValueError("starting_equity must be greater than zero.")
    return (ending_equity - starting_equity) / starting_equity * Decimal("100")


def calculate_max_drawdown_pct(equity_curve: list[EquityPoint]) -> Decimal:
    if not equity_curve:
        return Decimal("0")

    peak = equity_curve[0].equity
    max_drawdown = Decimal("0")
    for point in equity_curve:
        _validate_finite("equity", point.equity)
        if point.equity > peak:
            peak = point.equity
        if peak > 0:
            drawdown = (peak - point.equity) / peak * Decimal("100")
            if drawdown > max_drawdown:
                max_drawdown = drawdown
    return max_drawdown


def build_backtest_metrics(
    starting_equity: Decimal,
    ending_equity: Decimal,
    equity_curve: list[EquityPoint],
    trades: list[BacktestTrade],
    total_fees_paid: Decimal,
) -> BacktestMetrics:
    _validate_finite("total_fees_paid", total_fees_paid)
    return BacktestMetrics(
        starting_equity=starting_equity,
        ending_equity=ending_equity,
        total_return_pct=calculate_total_return_pct(starting_equity, ending_equity),
        max_drawdown_pct=calculate_max_drawdown_pct(equity_curve),
        total_trades=len(trades),
        winning_trades=0,
        losing_trades=0,
        total_fees_paid=total_fees_paid,
    )


def _validate_finite(name: str, value: Decimal) -> None:
    if not value.is_finite():
        raise ValueError(f"{name} must be finite.")

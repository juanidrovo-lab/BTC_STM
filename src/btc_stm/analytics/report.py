"""Performance report builder."""

from __future__ import annotations

from decimal import Decimal

from btc_stm.analytics.equity import analyze_equity_curve
from btc_stm.analytics.models import PerformanceReport
from btc_stm.analytics.trades import analyze_execution_reports
from btc_stm.backtesting.models import BacktestResult


def build_performance_report(backtest_result: BacktestResult) -> PerformanceReport:
    equity = analyze_equity_curve(backtest_result.equity_curve)
    execution_reports = [trade.execution_report for trade in backtest_result.trades]
    trades = analyze_execution_reports(execution_reports)
    warnings: list[str] = []

    if trades.total_reports == 0:
        warnings.append("Backtest produced no trades.")
    if trades.rejected_reports > 0:
        warnings.append("Backtest contains rejected execution reports.")
    if any(point.equity == 0 for point in backtest_result.equity_curve[:-1]):
        warnings.append("Equity curve contains zero equity; period return set to zero.")
    if equity.max_drawdown_pct > Decimal("20"):
        warnings.append("Max drawdown exceeded 20%.")
    if equity.ending_equity < equity.starting_equity:
        warnings.append("Ending equity is below starting equity.")

    return PerformanceReport(equity=equity, trades=trades, warnings=warnings)

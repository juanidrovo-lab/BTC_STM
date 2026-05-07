"""Local portfolio and performance analytics."""

from btc_stm.analytics.equity import (
    analyze_equity_curve,
    calculate_drawdown_points,
    calculate_return_points,
    validate_equity_curve,
)
from btc_stm.analytics.models import (
    DrawdownPoint,
    EquityCurveAnalysis,
    PerformanceReport,
    ReturnPoint,
    TradeAnalytics,
)
from btc_stm.analytics.report import build_performance_report
from btc_stm.analytics.trades import analyze_execution_reports

__all__ = [
    "DrawdownPoint",
    "EquityCurveAnalysis",
    "PerformanceReport",
    "ReturnPoint",
    "TradeAnalytics",
    "analyze_equity_curve",
    "analyze_execution_reports",
    "build_performance_report",
    "calculate_drawdown_points",
    "calculate_return_points",
    "validate_equity_curve",
]

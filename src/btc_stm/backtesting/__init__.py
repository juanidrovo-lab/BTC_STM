"""Deterministic local backtesting package."""

from btc_stm.backtesting.data_feed import HistoricalDataFeed
from btc_stm.backtesting.engine import BacktestEngine
from btc_stm.backtesting.metrics import (
    build_backtest_metrics,
    calculate_max_drawdown_pct,
    calculate_total_return_pct,
)
from btc_stm.backtesting.models import (
    BacktestConfig,
    BacktestMetrics,
    BacktestResult,
    BacktestTrade,
    EquityPoint,
    ScheduledOrder,
)

__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "BacktestMetrics",
    "BacktestResult",
    "BacktestTrade",
    "EquityPoint",
    "HistoricalDataFeed",
    "ScheduledOrder",
    "build_backtest_metrics",
    "calculate_max_drawdown_pct",
    "calculate_total_return_pct",
]

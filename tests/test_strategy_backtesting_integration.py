from datetime import UTC, datetime, timedelta
from decimal import Decimal

from btc_stm.backtesting.data_feed import HistoricalDataFeed
from btc_stm.backtesting.engine import BacktestEngine
from btc_stm.backtesting.models import BacktestConfig
from btc_stm.data.models import OHLCVBar
from btc_stm.domain import SymbolFilters
from btc_stm.execution.models import ExecutionStatus
from btc_stm.risk import RiskManager
from btc_stm.settings import Settings
from btc_stm.strategy.examples import OneShotBuyStrategy
from btc_stm.strategy.runner import StrategyRunner


def make_bar(open_time: datetime, close: Decimal = Decimal("100")) -> OHLCVBar:
    close_time = open_time + timedelta(minutes=1)
    return OHLCVBar(
        symbol="BTCUSDT",
        interval="1m",
        open_time=open_time,
        close_time=close_time,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=Decimal("1"),
        event_time=close_time,
        local_receive_time=close_time,
    )


def make_filters() -> SymbolFilters:
    return SymbolFilters(
        symbol="BTCUSDT",
        price_min=Decimal("1"),
        price_max=Decimal("1000000"),
        price_tick_size=Decimal("0.01"),
        qty_min=Decimal("0.001"),
        qty_max=Decimal("100"),
        qty_step_size=Decimal("0.001"),
        min_notional=Decimal("5"),
    )


def test_strategy_run_result_can_feed_backtest_engine() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    bars = [make_bar(start), make_bar(start + timedelta(minutes=1), close=Decimal("110"))]
    strategy_result = StrategyRunner(
        strategy=OneShotBuyStrategy(
            symbol="BTCUSDT",
            quantity=Decimal("1"),
            stop_loss_pct=Decimal("5"),
        ),
        symbol="BTCUSDT",
    ).run(bars)
    settings = Settings()

    backtest_result = BacktestEngine(
        settings=settings,
        risk_manager=RiskManager(settings),
        filters=make_filters(),
    ).run(
        config=BacktestConfig(
            symbol="BTCUSDT",
            initial_cash=Decimal("10000"),
            fee_rate_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
        ),
        data_feed=HistoricalDataFeed(bars),
        scheduled_orders=strategy_result.scheduled_orders,
    )

    assert backtest_result.trades[0].execution_report.status is ExecutionStatus.FILLED
    assert backtest_result.metrics.ending_equity == Decimal("10010")

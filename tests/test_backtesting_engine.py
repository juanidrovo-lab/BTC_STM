from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from btc_stm.backtesting.data_feed import HistoricalDataFeed
from btc_stm.backtesting.engine import BacktestEngine
from btc_stm.backtesting.models import BacktestConfig, ScheduledOrder
from btc_stm.data.models import OHLCVBar
from btc_stm.domain import OrderIntent, OrderSide, OrderType, SymbolFilters
from btc_stm.execution.models import ExecutionStatus
from btc_stm.risk import RiskManager
from btc_stm.settings import Settings, TradingMode


def make_bar(
    open_time: datetime,
    open_price: Decimal = Decimal("100"),
    close_price: Decimal = Decimal("100"),
) -> OHLCVBar:
    close_time = open_time + timedelta(minutes=1)
    return OHLCVBar(
        symbol="BTCUSDT",
        interval="1m",
        open_time=open_time,
        close_time=close_time,
        open=open_price,
        high=max(open_price, close_price),
        low=min(open_price, close_price),
        close=close_price,
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


def make_order(stop_loss: Decimal | None = Decimal("90")) -> OrderIntent:
    return OrderIntent(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1"),
        price=Decimal("100"),
        stop_loss=stop_loss,
    )


def make_config(execute_on: str = "close") -> BacktestConfig:
    return BacktestConfig(
        symbol="BTCUSDT",
        initial_cash=Decimal("10000"),
        fee_rate_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        execute_on=execute_on,
    )


def make_engine(settings: Settings | None = None) -> BacktestEngine:
    settings = settings or Settings()
    return BacktestEngine(
        settings=settings,
        risk_manager=RiskManager(settings),
        filters=make_filters(),
    )


def test_backtest_engine_executes_scheduled_buy_and_updates_equity_curve() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    feed = HistoricalDataFeed(
        [
            make_bar(start, close_price=Decimal("100")),
            make_bar(start + timedelta(minutes=1), close_price=Decimal("110")),
        ]
    )

    result = make_engine().run(
        config=make_config(),
        data_feed=feed,
        scheduled_orders=[ScheduledOrder(execute_at=start, order=make_order())],
    )

    assert len(result.equity_curve) == 2
    assert result.equity_curve[0].equity == Decimal("10000")
    assert result.equity_curve[1].equity == Decimal("10010")
    assert result.metrics.ending_equity == Decimal("10010")


def test_backtest_engine_records_filled_execution_report() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    feed = HistoricalDataFeed([make_bar(start)])

    result = make_engine().run(
        config=make_config(),
        data_feed=feed,
        scheduled_orders=[ScheduledOrder(execute_at=start, order=make_order())],
    )

    assert len(result.trades) == 1
    assert result.trades[0].execution_report.status is ExecutionStatus.FILLED


def test_backtest_engine_records_rejected_execution_report() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    feed = HistoricalDataFeed([make_bar(start)])

    result = make_engine().run(
        config=make_config(),
        data_feed=feed,
        scheduled_orders=[ScheduledOrder(execute_at=start, order=make_order(stop_loss=None))],
    )

    assert len(result.trades) == 1
    assert result.trades[0].execution_report.status is ExecutionStatus.REJECTED
    assert result.trades[0].execution_report.reason is not None
    assert "stop-loss" in result.trades[0].execution_report.reason


def test_backtest_engine_does_not_execute_orders_outside_historical_range() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    feed = HistoricalDataFeed([make_bar(start)])

    result = make_engine().run(
        config=make_config(),
        data_feed=feed,
        scheduled_orders=[
            ScheduledOrder(execute_at=start + timedelta(days=1), order=make_order())
        ],
    )

    assert result.trades == []
    assert len(result.equity_curve) == 1


def test_backtest_engine_rejects_live_mode() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    settings = Settings(trading_mode=TradingMode.LIVE, enable_live_trading=True)

    with pytest.raises(ValueError, match="paper mode"):
        make_engine(settings).run(
            config=make_config(),
            data_feed=HistoricalDataFeed([make_bar(start)]),
            scheduled_orders=[],
        )


def test_backtest_engine_uses_open_price_when_configured() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    feed = HistoricalDataFeed([make_bar(start, open_price=Decimal("95"), close_price=Decimal("100"))])

    result = make_engine().run(
        config=make_config(execute_on="open"),
        data_feed=feed,
        scheduled_orders=[ScheduledOrder(execute_at=start, order=make_order())],
    )

    assert result.trades[0].execution_report.average_fill_price == Decimal("95")

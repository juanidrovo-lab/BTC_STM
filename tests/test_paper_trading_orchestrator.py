from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from btc_stm.analytics.models import PerformanceReport
from btc_stm.data.models import OHLCVBar
from btc_stm.domain import OrderIntent, OrderSide, OrderType, SymbolFilters
from btc_stm.execution.models import ExecutionStatus
from btc_stm.orchestration.models import OrchestratorEventType, PaperTradingConfig
from btc_stm.orchestration.paper_trading import PaperTradingOrchestrator
from btc_stm.risk import RiskManager
from btc_stm.settings import Settings, TradingMode
from btc_stm.strategy.base import Strategy
from btc_stm.strategy.models import StrategyContext, StrategyDecision


def make_bar(
    open_time: datetime,
    *,
    symbol: str = "BTCUSDT",
    open_price: Decimal = Decimal("100"),
    close_price: Decimal = Decimal("100"),
) -> OHLCVBar:
    close_time = open_time + timedelta(minutes=1)
    return OHLCVBar(
        symbol=symbol,
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


def make_filters(symbol: str = "BTCUSDT") -> SymbolFilters:
    return SymbolFilters(
        symbol=symbol,
        price_min=Decimal("1"),
        price_max=Decimal("1000000"),
        price_tick_size=Decimal("0.01"),
        qty_min=Decimal("0.001"),
        qty_max=Decimal("100"),
        qty_step_size=Decimal("0.001"),
        min_notional=Decimal("5"),
    )


def make_config(execute_on: str = "close") -> PaperTradingConfig:
    return PaperTradingConfig(
        symbol="BTCUSDT",
        initial_cash=Decimal("10000"),
        fee_rate_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        execute_on=execute_on,
    )


def make_order(
    *,
    symbol: str = "BTCUSDT",
    quantity: Decimal = Decimal("1"),
    stop_loss: Decimal | None = Decimal("90"),
) -> OrderIntent:
    return OrderIntent(
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=quantity,
        price=Decimal("100"),
        stop_loss=stop_loss,
    )


class RecordingStrategy:
    name = "recording"

    def __init__(
        self,
        *,
        order: OrderIntent | None = None,
        timestamp_offset: timedelta = timedelta(0),
    ) -> None:
        self.order = order
        self.timestamp_offset = timestamp_offset
        self.contexts: list[StrategyContext] = []
        self.calls = 0

    def on_bar(self, context: StrategyContext) -> StrategyDecision:
        self.contexts.append(context)
        self.calls += 1
        orders = [self.order] if self.order is not None and self.calls == 1 else []
        return StrategyDecision(
            strategy_name=self.name,
            timestamp=context.current_bar.open_time + self.timestamp_offset,
            orders=orders,
        )


class BadTimestampStrategy:
    name = "bad_timestamp"

    def on_bar(self, context: StrategyContext) -> StrategyDecision:
        return StrategyDecision(
            strategy_name=self.name,
            timestamp=context.current_bar.open_time - timedelta(seconds=1),
            orders=[],
        )


def make_orchestrator(
    strategy: Strategy,
    *,
    settings: Settings | None = None,
    filters: SymbolFilters | None = None,
) -> PaperTradingOrchestrator:
    settings = settings or Settings()
    return PaperTradingOrchestrator(
        settings=settings,
        risk_manager=RiskManager(settings),
        filters=filters or make_filters(),
        strategy=strategy,
    )


def test_orchestrator_rejects_live_mode() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    settings = Settings(trading_mode=TradingMode.LIVE, enable_live_trading=True)

    with pytest.raises(ValueError, match="paper mode"):
        make_orchestrator(RecordingStrategy(), settings=settings).run(
            make_config(),
            [make_bar(start)],
        )


def test_orchestrator_rejects_filter_symbol_mismatch() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="filters"):
        make_orchestrator(RecordingStrategy(), filters=make_filters("ETHUSDT")).run(
            make_config(),
            [make_bar(start)],
        )


def test_orchestrator_rejects_bar_symbol_mismatch() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="bars"):
        make_orchestrator(RecordingStrategy()).run(
            make_config(),
            [make_bar(start, symbol="ETHUSDT")],
        )


def test_orchestrator_does_not_deliver_future_bars_to_strategy_context() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    strategy = RecordingStrategy()
    bars = [
        make_bar(start),
        make_bar(start + timedelta(minutes=1)),
        make_bar(start + timedelta(minutes=2)),
    ]

    make_orchestrator(strategy).run(make_config(), bars)

    for context in strategy.contexts:
        assert all(
            bar.open_time <= context.current_bar.open_time for bar in context.history
        )


def test_orchestrator_schedules_orders_with_decision_timestamp() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    strategy = RecordingStrategy(
        order=make_order(),
        timestamp_offset=timedelta(minutes=1),
    )
    bars = [make_bar(start), make_bar(start + timedelta(minutes=1))]

    result = make_orchestrator(strategy).run(make_config(), bars)

    scheduled_event = next(
        event for event in result.events if event.event_type is OrchestratorEventType.ORDER_SCHEDULED
    )
    assert scheduled_event.timestamp == start + timedelta(minutes=1)
    assert result.execution_reports[0].status is ExecutionStatus.FILLED


def test_orchestrator_does_not_execute_order_generated_on_same_bar() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    strategy = RecordingStrategy(order=make_order())

    result = make_orchestrator(strategy).run(make_config(), [make_bar(start)])

    assert result.execution_reports == []
    assert any(
        event.event_type is OrchestratorEventType.ORDER_SCHEDULED
        for event in result.events
    )
    assert not any(
        event.event_type is OrchestratorEventType.ORDER_EXECUTED
        for event in result.events
    )


def test_orchestrator_executes_first_bar_order_on_second_bar() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    strategy = RecordingStrategy(order=make_order())
    bars = [make_bar(start), make_bar(start + timedelta(minutes=1), close_price=Decimal("110"))]

    result = make_orchestrator(strategy).run(make_config(), bars)

    assert len(result.execution_reports) == 1
    assert result.execution_reports[0].status is ExecutionStatus.FILLED
    assert result.execution_reports[0].average_fill_price == Decimal("110")
    executed_event = next(
        event for event in result.events if event.event_type is OrchestratorEventType.ORDER_EXECUTED
    )
    assert executed_event.timestamp == start + timedelta(minutes=1)


def test_orchestrator_execute_on_open_uses_next_bar_open_without_future_close() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    strategy = RecordingStrategy(order=make_order())
    bars = [
        make_bar(start, open_price=Decimal("100"), close_price=Decimal("1000")),
        make_bar(
            start + timedelta(minutes=1),
            open_price=Decimal("95"),
            close_price=Decimal("95"),
        ),
    ]

    result = make_orchestrator(strategy).run(make_config(execute_on="open"), bars)

    assert len(result.execution_reports) == 1
    assert result.execution_reports[0].average_fill_price == Decimal("95")


def test_orchestrator_rejects_decision_timestamp_before_current_bar() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="timestamp"):
        make_orchestrator(BadTimestampStrategy()).run(
            make_config(),
            [make_bar(start)],
        )


def test_orchestrator_rejects_orders_without_stop_loss() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    strategy = RecordingStrategy(order=make_order(stop_loss=None))

    with pytest.raises(ValueError, match="stop_loss"):
        make_orchestrator(strategy).run(make_config(), [make_bar(start)])


def test_orchestrator_rejects_orders_with_symbol_mismatch() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    strategy = RecordingStrategy(order=make_order(symbol="ETHUSDT"))

    with pytest.raises(ValueError, match="symbol"):
        make_orchestrator(strategy).run(make_config(), [make_bar(start)])


def test_orchestrator_executes_paper_buy_and_records_filled_report() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    strategy = RecordingStrategy(order=make_order())
    bars = [make_bar(start), make_bar(start + timedelta(minutes=1))]

    result = make_orchestrator(strategy).run(make_config(), bars)

    assert result.execution_reports[0].status is ExecutionStatus.FILLED
    assert result.performance_report.trades.filled_reports == 1
    assert any(
        event.event_type is OrchestratorEventType.ORDER_EXECUTED
        for event in result.events
    )


def test_orchestrator_records_order_rejected_when_risk_manager_rejects() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    strategy = RecordingStrategy(order=make_order(quantity=Decimal("200")))
    bars = [make_bar(start), make_bar(start + timedelta(minutes=1))]

    result = make_orchestrator(strategy).run(make_config(), bars)

    assert result.execution_reports[0].status is ExecutionStatus.REJECTED
    assert result.performance_report.trades.rejected_reports == 1
    rejected_event = next(
        event for event in result.events if event.event_type is OrchestratorEventType.ORDER_REJECTED
    )
    assert rejected_event.timestamp == start + timedelta(minutes=1)


def test_orchestrator_generates_equity_curve_and_performance_report() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    bars = [make_bar(start), make_bar(start + timedelta(minutes=1), close_price=Decimal("110"))]
    strategy = RecordingStrategy(order=make_order())

    result = make_orchestrator(strategy).run(make_config(), bars)

    assert len(result.equity_curve) == len(bars)
    assert isinstance(result.performance_report, PerformanceReport)
    assert result.performance_report.equity.ending_equity == Decimal("10000")


def test_orchestrator_records_session_completed_and_core_events() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)

    result = make_orchestrator(RecordingStrategy()).run(
        make_config(),
        [make_bar(start)],
    )

    event_types = {event.event_type for event in result.events}
    assert OrchestratorEventType.BAR_RECEIVED in event_types
    assert OrchestratorEventType.STRATEGY_DECISION in event_types
    assert OrchestratorEventType.EQUITY_UPDATED in event_types
    assert OrchestratorEventType.SESSION_COMPLETED in event_types


def test_orchestrator_omits_orders_after_historical_range() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    strategy = RecordingStrategy(
        order=make_order(),
        timestamp_offset=timedelta(days=1),
    )

    result = make_orchestrator(strategy).run(make_config(), [make_bar(start)])

    assert result.execution_reports == []
    assert not any(
        event.event_type is OrchestratorEventType.ORDER_SCHEDULED
        for event in result.events
    )


def test_orchestrator_records_session_failed_before_reraising() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    orchestrator = make_orchestrator(BadTimestampStrategy())

    with pytest.raises(ValueError, match="timestamp"):
        orchestrator.run(make_config(), [make_bar(start)])

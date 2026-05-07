from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from btc_stm.data.models import OHLCVBar
from btc_stm.domain import OrderIntent, OrderSide, OrderType
from btc_stm.strategy.models import StrategyContext, StrategyDecision
from btc_stm.strategy.runner import StrategyRunner


def make_bar(open_time: datetime) -> OHLCVBar:
    close_time = open_time + timedelta(minutes=1)
    return OHLCVBar(
        symbol="BTCUSDT",
        interval="1m",
        open_time=open_time,
        close_time=close_time,
        open=Decimal("100"),
        high=Decimal("100"),
        low=Decimal("100"),
        close=Decimal("100"),
        volume=Decimal("1"),
        event_time=close_time,
        local_receive_time=close_time,
    )


def make_order(symbol: str = "BTCUSDT", stop_loss: Decimal | None = Decimal("90")) -> OrderIntent:
    return OrderIntent(
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1"),
        price=Decimal("100"),
        stop_loss=stop_loss,
    )


class RecordingStrategy:
    name = "recording"

    def __init__(self, order: OrderIntent | None = None) -> None:
        self.contexts: list[StrategyContext] = []
        self.order = order

    def on_bar(self, context: StrategyContext) -> StrategyDecision:
        self.contexts.append(context)
        return StrategyDecision(
            strategy_name=self.name,
            timestamp=context.current_bar.open_time,
            orders=[] if self.order is None else [self.order],
        )


class FutureTimestampStrategy:
    name = "future_timestamp"

    def on_bar(self, context: StrategyContext) -> StrategyDecision:
        return StrategyDecision(
            strategy_name=self.name,
            timestamp=context.current_bar.open_time + timedelta(minutes=1),
            orders=[make_order()],
        )


class PastTimestampStrategy:
    name = "past_timestamp"

    def on_bar(self, context: StrategyContext) -> StrategyDecision:
        return StrategyDecision(
            strategy_name=self.name,
            timestamp=context.current_bar.open_time - timedelta(minutes=1),
            orders=[make_order()],
        )


def test_strategy_runner_does_not_deliver_future_bars() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    strategy = RecordingStrategy()
    bars = [make_bar(start), make_bar(start + timedelta(minutes=1))]

    StrategyRunner(strategy=strategy, symbol="BTCUSDT").run(bars)

    for context in strategy.contexts:
        assert all(bar.open_time <= context.current_bar.open_time for bar in context.history)


def test_strategy_runner_converts_orders_to_scheduled_orders() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    result = StrategyRunner(
        strategy=RecordingStrategy(order=make_order()),
        symbol="BTCUSDT",
    ).run([make_bar(start)])

    assert len(result.scheduled_orders) == 1
    assert result.scheduled_orders[0].execute_at == start


def test_strategy_runner_uses_decision_timestamp_for_scheduled_orders() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    result = StrategyRunner(
        strategy=FutureTimestampStrategy(),
        symbol="BTCUSDT",
    ).run([make_bar(start), make_bar(start + timedelta(minutes=1))])

    assert result.scheduled_orders[0].execute_at == start + timedelta(minutes=1)


def test_strategy_runner_rejects_decision_timestamp_before_current_bar() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="timestamp"):
        StrategyRunner(strategy=PastTimestampStrategy(), symbol="BTCUSDT").run([make_bar(start)])


def test_strategy_runner_rejects_order_symbol_mismatch() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="symbol"):
        StrategyRunner(
            strategy=RecordingStrategy(order=make_order("ETHUSDT")),
            symbol="BTCUSDT",
        ).run([make_bar(start)])


def test_strategy_runner_rejects_orders_without_stop_loss() -> None:
    class BadStrategy:
        name = "bad"

        def on_bar(self, context: StrategyContext) -> StrategyDecision:
            order = OrderIntent.model_construct(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=Decimal("1"),
                price=Decimal("100"),
                stop_loss=None,
            )
            return StrategyDecision.model_construct(
                strategy_name=self.name,
                timestamp=context.current_bar.open_time,
                orders=[order],
            )

    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="stop_loss"):
        StrategyRunner(strategy=BadStrategy(), symbol="BTCUSDT").run([make_bar(start)])

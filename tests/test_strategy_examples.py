from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from btc_stm.data.models import OHLCVBar
from btc_stm.strategy.examples import NoOpStrategy, OneShotBuyStrategy
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


def test_noop_strategy_generates_no_orders() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    result = StrategyRunner(strategy=NoOpStrategy(), symbol="BTCUSDT").run([make_bar(start)])

    assert result.scheduled_orders == []
    assert result.decisions[0].orders == []


def test_one_shot_buy_strategy_generates_single_order() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    strategy = OneShotBuyStrategy(
        symbol="BTCUSDT",
        quantity=Decimal("1"),
        stop_loss_pct=Decimal("5"),
    )
    result = StrategyRunner(strategy=strategy, symbol="BTCUSDT").run(
        [make_bar(start), make_bar(start + timedelta(minutes=1))]
    )

    assert len(result.scheduled_orders) == 1
    assert result.scheduled_orders[0].order.price == Decimal("100")


def test_one_shot_buy_strategy_does_not_buy_twice() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    strategy = OneShotBuyStrategy(
        symbol="BTCUSDT",
        quantity=Decimal("1"),
        stop_loss_pct=Decimal("5"),
    )

    result = StrategyRunner(strategy=strategy, symbol="BTCUSDT").run(
        [make_bar(start), make_bar(start + timedelta(minutes=1))]
    )

    assert sum(len(decision.orders) for decision in result.decisions) == 1


def test_one_shot_buy_strategy_calculates_stop_loss_with_decimal() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    strategy = OneShotBuyStrategy(
        symbol="BTCUSDT",
        quantity=Decimal("1"),
        stop_loss_pct=Decimal("5"),
    )

    result = StrategyRunner(strategy=strategy, symbol="BTCUSDT").run(
        [make_bar(start, close=Decimal("200"))]
    )

    assert result.scheduled_orders[0].order.stop_loss == Decimal("190.00")


def test_one_shot_buy_strategy_rejects_invalid_parameters() -> None:
    with pytest.raises(ValueError):
        OneShotBuyStrategy(symbol="BTCUSDT", quantity=Decimal("0"), stop_loss_pct=Decimal("5"))
    with pytest.raises(ValueError):
        OneShotBuyStrategy(symbol="BTCUSDT", quantity=Decimal("1"), stop_loss_pct=Decimal("100"))

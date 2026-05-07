from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from btc_stm.data.models import OHLCVBar
from btc_stm.domain import OrderIntent, OrderSide, OrderType
from btc_stm.strategy.models import StrategyContext, StrategyDecision


def make_bar(open_time: datetime, symbol: str = "BTCUSDT") -> OHLCVBar:
    close_time = open_time + timedelta(minutes=1)
    return OHLCVBar(
        symbol=symbol,
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


def make_order(stop_loss: Decimal | None = Decimal("90")) -> OrderIntent:
    return OrderIntent(
        symbol="btcusdt",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1"),
        price=Decimal("100"),
        stop_loss=stop_loss,
    )


def test_strategy_context_rejects_current_bar_symbol_mismatch() -> None:
    now = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="current_bar"):
        StrategyContext(symbol="BTCUSDT", current_bar=make_bar(now, "ETHUSDT"), history=[])


def test_strategy_context_rejects_history_symbol_mismatch() -> None:
    now = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="history"):
        StrategyContext(
            symbol="BTCUSDT",
            current_bar=make_bar(now),
            history=[make_bar(now, "ETHUSDT")],
        )


def test_strategy_context_rejects_future_history() -> None:
    now = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="future"):
        StrategyContext(
            symbol="BTCUSDT",
            current_bar=make_bar(now),
            history=[make_bar(now + timedelta(minutes=1))],
        )


def test_strategy_context_rejects_duplicate_history_timestamps() -> None:
    now = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="duplicate"):
        StrategyContext(
            symbol="BTCUSDT",
            current_bar=make_bar(now),
            history=[make_bar(now), make_bar(now)],
        )


def test_strategy_context_allows_history_including_current_bar() -> None:
    now = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    context = StrategyContext(
        symbol="BTC/USDT",
        current_bar=make_bar(now),
        history=[make_bar(now)],
    )

    assert context.symbol == "BTCUSDT"


def test_strategy_decision_rejects_orders_without_stop_loss() -> None:
    with pytest.raises(ValidationError, match="stop_loss"):
        StrategyDecision(
            strategy_name="test",
            timestamp=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
            orders=[make_order(stop_loss=None)],
        )


def test_strategy_decision_rejects_empty_strategy_name() -> None:
    with pytest.raises(ValidationError, match="strategy_name"):
        StrategyDecision(
            strategy_name=" ",
            timestamp=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
            orders=[],
        )

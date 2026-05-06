from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from btc_stm.data.models import OHLCVBar, OrderBookLevel, OrderBookSnapshot, TradeEvent


def now() -> datetime:
    return datetime(2026, 5, 6, 12, 0, tzinfo=UTC)


def test_trade_event_rejects_non_positive_price() -> None:
    with pytest.raises(ValidationError, match="greater than 0"):
        TradeEvent(
            symbol="BTCUSDT",
            trade_id=1,
            price=Decimal("0"),
            quantity=Decimal("0.01"),
            event_time=now(),
            local_receive_time=now(),
        )


def test_trade_event_rejects_non_positive_quantity() -> None:
    with pytest.raises(ValidationError, match="greater than 0"):
        TradeEvent(
            symbol="BTCUSDT",
            trade_id=1,
            price=Decimal("50000"),
            quantity=Decimal("0"),
            event_time=now(),
            local_receive_time=now(),
        )


@pytest.mark.parametrize(
    ("raw_symbol", "expected"),
    [
        ("btcusdt", "BTCUSDT"),
        ("BTC/USDT", "BTCUSDT"),
        ("BTC-USDT", "BTCUSDT"),
    ],
)
def test_symbol_normalization(raw_symbol: str, expected: str) -> None:
    event = TradeEvent(
        symbol=raw_symbol,
        trade_id="100",
        price=Decimal("50000"),
        quantity=Decimal("0.01"),
        event_time=now(),
        local_receive_time=now(),
    )

    assert event.symbol == expected


def test_order_book_snapshot_rejects_empty_book() -> None:
    with pytest.raises(ValidationError):
        OrderBookSnapshot(
            symbol="BTCUSDT",
            last_update_id=10,
            bids=[],
            asks=[],
            event_time=now(),
            local_receive_time=now(),
        )


def test_order_book_snapshot_rejects_crossed_book() -> None:
    with pytest.raises(ValidationError, match="best_bid"):
        OrderBookSnapshot(
            symbol="BTCUSDT",
            last_update_id=10,
            bids=[OrderBookLevel(price=Decimal("50001"), quantity=Decimal("0.1"))],
            asks=[OrderBookLevel(price=Decimal("50000"), quantity=Decimal("0.1"))],
            event_time=now(),
            local_receive_time=now(),
        )


def test_ohlcv_bar_rejects_incoherent_ranges() -> None:
    with pytest.raises(ValidationError, match="high"):
        OHLCVBar(
            symbol="BTCUSDT",
            interval="1m",
            open_time=now(),
            close_time=now() + timedelta(minutes=1),
            open=Decimal("100"),
            high=Decimal("99"),
            low=Decimal("95"),
            close=Decimal("98"),
            volume=Decimal("10"),
            event_time=now() + timedelta(minutes=1),
            local_receive_time=now() + timedelta(minutes=1),
        )


def test_ohlcv_bar_rejects_non_increasing_close_time() -> None:
    with pytest.raises(ValidationError, match="close_time"):
        OHLCVBar(
            symbol="BTCUSDT",
            interval="1m",
            open_time=now(),
            close_time=now(),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("10"),
            event_time=now(),
            local_receive_time=now(),
        )

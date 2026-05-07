from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from btc_stm.data.binance_parsers import (
    parse_kline_event,
    parse_order_book_delta,
    parse_order_book_snapshot,
    parse_trade_event,
)


def now() -> datetime:
    return datetime(2026, 5, 6, 12, 0, tzinfo=UTC)


def test_parse_order_book_snapshot_converts_levels() -> None:
    snapshot = parse_order_book_snapshot(
        symbol="btcusdt",
        payload={
            "lastUpdateId": 123,
            "bids": [["50000.10", "0.25"]],
            "asks": [["50001.20", "0.50"]],
        },
        event_time=now(),
        local_receive_time=now(),
    )

    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.last_update_id == 123
    assert snapshot.bids[0].price == Decimal("50000.10")
    assert snapshot.bids[0].quantity == Decimal("0.25")
    assert snapshot.asks[0].price == Decimal("50001.20")
    assert snapshot.asks[0].quantity == Decimal("0.50")


def test_parse_order_book_snapshot_rejects_invalid_spread() -> None:
    with pytest.raises(ValidationError, match="best_bid"):
        parse_order_book_snapshot(
            symbol="BTCUSDT",
            payload={
                "lastUpdateId": 123,
                "bids": [["50001.00", "0.25"]],
                "asks": [["50001.00", "0.50"]],
            },
            event_time=now(),
            local_receive_time=now(),
        )


def test_parse_order_book_snapshot_rejects_incomplete_payload() -> None:
    with pytest.raises(ValueError, match="asks"):
        parse_order_book_snapshot(
            symbol="BTCUSDT",
            payload={"lastUpdateId": 123, "bids": [["50000.00", "0.25"]]},
            event_time=now(),
            local_receive_time=now(),
        )


def test_parse_trade_event_converts_decimal_values() -> None:
    event = parse_trade_event(
        symbol="BTC/USDT",
        payload={
            "t": 456,
            "p": "50000.25",
            "q": "0.010",
            "T": 1_778_068_800_000,
            "m": True,
        },
        local_receive_time=datetime(2026, 5, 6, 12, 1, tzinfo=UTC),
    )

    assert event.symbol == "BTCUSDT"
    assert event.trade_id == 456
    assert event.price == Decimal("50000.25")
    assert event.quantity == Decimal("0.010")
    assert event.event_time == datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    assert event.is_buyer_maker is True


def test_parse_trade_event_rejects_non_positive_price() -> None:
    with pytest.raises(ValidationError):
        parse_trade_event(
            symbol="BTCUSDT",
            payload={"t": 456, "p": "0", "q": "0.010", "T": 1_778_068_800_000},
            local_receive_time=datetime(2026, 5, 6, 12, 1, tzinfo=UTC),
        )


def test_parse_kline_event_converts_ohlcv() -> None:
    event = parse_kline_event(
        symbol="BTC-USDT",
        payload={
            "E": 1_778_068_860_000,
            "k": {
                "i": "1m",
                "t": 1_778_068_800_000,
                "T": 1_778_068_860_000,
                "o": "100.00",
                "h": "110.00",
                "l": "90.00",
                "c": "105.00",
                "v": "12.5",
            },
        },
        local_receive_time=datetime(2026, 5, 6, 12, 1, tzinfo=UTC),
    )

    assert event.symbol == "BTCUSDT"
    assert event.interval == "1m"
    assert event.open == Decimal("100.00")
    assert event.high == Decimal("110.00")
    assert event.low == Decimal("90.00")
    assert event.close == Decimal("105.00")
    assert event.volume == Decimal("12.5")


def test_parse_order_book_delta_converts_update_ids_and_levels() -> None:
    delta = parse_order_book_delta(
        symbol="BTCUSDT",
        payload={
            "E": 1_778_068_800_000,
            "U": 10,
            "u": 12,
            "b": [["50000.00", "0.00"]],
            "a": [["50001.00", "0.30"]],
        },
        local_receive_time=datetime(2026, 5, 6, 12, 1, tzinfo=UTC),
    )

    assert delta.first_update_id == 10
    assert delta.final_update_id == 12
    assert delta.bids[0].quantity == Decimal("0.00")
    assert delta.asks[0].price == Decimal("50001.00")

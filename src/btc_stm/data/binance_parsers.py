"""Pure parsers for Binance public market data payloads."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import SupportsInt, cast

from btc_stm.data.binance_types import JsonArray, JsonObject
from btc_stm.data.models import (
    OHLCVBar,
    OrderBookDelta,
    OrderBookLevel,
    OrderBookSnapshot,
    TradeEvent,
)

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def parse_order_book_snapshot(
    symbol: str,
    payload: JsonObject,
    event_time: datetime,
    local_receive_time: datetime,
) -> OrderBookSnapshot:
    last_update_id = _int(_require(payload, "lastUpdateId"))
    return OrderBookSnapshot(
        symbol=symbol,
        last_update_id=last_update_id,
        bids=_parse_levels(_require_list(payload, "bids")),
        asks=_parse_levels(_require_list(payload, "asks")),
        event_time=event_time,
        local_receive_time=local_receive_time,
    )


def parse_trade_event(
    symbol: str,
    payload: JsonObject,
    local_receive_time: datetime,
) -> TradeEvent:
    return TradeEvent(
        symbol=symbol,
        trade_id=_trade_id(_require(payload, "t")),
        price=_decimal(_require(payload, "p")),
        quantity=_decimal(_require(payload, "q")),
        event_time=_datetime_from_ms(_require(payload, "T")),
        local_receive_time=local_receive_time,
        is_buyer_maker=bool(_require(payload, "m")) if "m" in payload else None,
    )


def parse_kline_event(
    symbol: str,
    payload: JsonObject,
    local_receive_time: datetime,
) -> OHLCVBar:
    kline = _require_object(payload, "k")
    return OHLCVBar(
        symbol=symbol,
        interval=str(_require(kline, "i")),
        open_time=_datetime_from_ms(_require(kline, "t")),
        close_time=_datetime_from_ms(_require(kline, "T")),
        open=_decimal(_require(kline, "o")),
        high=_decimal(_require(kline, "h")),
        low=_decimal(_require(kline, "l")),
        close=_decimal(_require(kline, "c")),
        volume=_decimal(_require(kline, "v")),
        event_time=_datetime_from_ms(_require(payload, "E")),
        local_receive_time=local_receive_time,
    )


def parse_order_book_delta(
    symbol: str,
    payload: JsonObject,
    local_receive_time: datetime,
) -> OrderBookDelta:
    return OrderBookDelta(
        symbol=symbol,
        first_update_id=_int(_require(payload, "U")),
        final_update_id=_int(_require(payload, "u")),
        bids=_parse_levels(_require_list(payload, "b")),
        asks=_parse_levels(_require_list(payload, "a")),
        event_time=_datetime_from_ms(_require(payload, "E")),
        local_receive_time=local_receive_time,
    )


def _parse_levels(raw_levels: JsonArray) -> list[OrderBookLevel]:
    levels: list[OrderBookLevel] = []
    for raw_level in raw_levels:
        if not isinstance(raw_level, list | tuple) or len(raw_level) < 2:
            raise ValueError("Binance order book level must include price and quantity.")
        levels.append(
            OrderBookLevel(
                price=_decimal(raw_level[0]),
                quantity=_decimal(raw_level[1]),
            )
        )
    return levels


def _require(payload: JsonObject, key: str) -> object:
    if key not in payload:
        raise ValueError(f"Missing Binance payload field: {key}")
    return payload[key]


def _require_list(payload: JsonObject, key: str) -> JsonArray:
    value = _require(payload, key)
    if not isinstance(value, list):
        raise ValueError(f"Binance payload field must be a list: {key}")
    return value


def _require_object(payload: JsonObject, key: str) -> JsonObject:
    value = _require(payload, key)
    if not isinstance(value, dict):
        raise ValueError(f"Binance payload field must be an object: {key}")
    return cast(JsonObject, value)


def _decimal(value: object) -> Decimal:
    decimal_value = Decimal(str(value))
    if not decimal_value.is_finite():
        raise ValueError("Binance numeric field must be finite.")
    return decimal_value


def _datetime_from_ms(value: object) -> datetime:
    milliseconds = _int(value)
    return EPOCH + timedelta(milliseconds=milliseconds)


def _int(value: object) -> int:
    if isinstance(value, str | bytes | bytearray):
        return int(value)
    if isinstance(value, SupportsInt):
        return int(value)
    raise ValueError("Binance integer field must be int-compatible.")


def _trade_id(value: object) -> str | int:
    if isinstance(value, str | int):
        return value
    raise ValueError("Binance trade id must be a string or integer.")

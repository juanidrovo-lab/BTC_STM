"""Quality checks for normalized public market data."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from btc_stm.data.models import (
    LOCAL_RECEIVE_TIME_TOLERANCE,
    OHLCVBar,
    OrderBookDelta,
    OrderBookLevel,
    OrderBookSnapshot,
    TradeEvent,
)


class DataQualityResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def validate_trade_event(event: TradeEvent) -> DataQualityResult:
    errors: list[str] = []
    warnings: list[str] = []

    _validate_positive("price", event.price, errors)
    _validate_positive("quantity", event.quantity, errors)
    _validate_timestamps(event.event_time, event.local_receive_time, errors)

    return _result(errors, warnings)


def validate_order_book_snapshot(snapshot: OrderBookSnapshot) -> DataQualityResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not snapshot.bids:
        errors.append("Order book snapshot must include at least one bid.")
    if not snapshot.asks:
        errors.append("Order book snapshot must include at least one ask.")
    if snapshot.bids and snapshot.asks:
        _validate_spread(
            best_bid=max(level.price for level in snapshot.bids),
            best_ask=min(level.price for level in snapshot.asks),
            errors=errors,
        )
    _validate_timestamps(snapshot.event_time, snapshot.local_receive_time, errors)

    return _result(errors, warnings)


def validate_order_book_delta(delta: OrderBookDelta) -> DataQualityResult:
    errors: list[str] = []
    warnings: list[str] = []

    if delta.final_update_id < delta.first_update_id:
        errors.append("final_update_id must be greater than or equal to first_update_id.")
    _validate_levels(delta.bids, "bid", errors)
    _validate_levels(delta.asks, "ask", errors)
    _validate_timestamps(delta.event_time, delta.local_receive_time, errors)

    return _result(errors, warnings)


def validate_ohlcv_bar(bar: OHLCVBar) -> DataQualityResult:
    errors: list[str] = []
    warnings: list[str] = []

    if bar.close_time <= bar.open_time:
        errors.append("close_time must be greater than open_time.")
    if bar.high < bar.open or bar.high < bar.close or bar.high < bar.low:
        errors.append("high must be greater than or equal to open, close, and low.")
    if bar.low > bar.open or bar.low > bar.close:
        errors.append("low must be less than or equal to open and close.")
    if bar.volume < 0:
        errors.append("volume must be greater than or equal to zero.")
    _validate_timestamps(bar.event_time, bar.local_receive_time, errors)

    return _result(errors, warnings)


def _result(errors: list[str], warnings: list[str]) -> DataQualityResult:
    return DataQualityResult(valid=not errors, errors=errors, warnings=warnings)


def _validate_positive(field_name: str, value: Decimal, errors: list[str]) -> None:
    if value <= 0:
        errors.append(f"{field_name} must be greater than zero.")


def _validate_levels(
    levels: Sequence[OrderBookLevel],
    side: str,
    errors: list[str],
) -> None:
    for index, level in enumerate(levels):
        if level.price <= 0:
            errors.append(f"{side} level {index} price must be greater than zero.")
        if level.quantity < 0:
            errors.append(f"{side} level {index} quantity must be greater than or equal to zero.")


def _validate_spread(best_bid: Decimal, best_ask: Decimal, errors: list[str]) -> None:
    if best_bid >= best_ask:
        errors.append("best_bid must be lower than best_ask.")


def _validate_timestamps(
    event_time: datetime,
    local_receive_time: datetime,
    errors: list[str],
) -> None:
    if local_receive_time + LOCAL_RECEIVE_TIME_TOLERANCE < event_time:
        errors.append(
            "local_receive_time must not be earlier than event_time beyond "
            "1 second clock skew tolerance."
        )

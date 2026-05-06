from datetime import UTC, datetime
from decimal import Decimal

from btc_stm.data.models import OHLCVBar, OrderBookDelta, OrderBookLevel, OrderBookSnapshot, TradeEvent
from btc_stm.data.quality import (
    DataQualityResult,
    validate_ohlcv_bar,
    validate_order_book_delta,
    validate_order_book_snapshot,
    validate_trade_event,
)


def now() -> datetime:
    return datetime(2026, 5, 6, 12, 0, tzinfo=UTC)


def test_data_quality_result_returns_expected_trade_errors() -> None:
    event = TradeEvent.model_construct(
        symbol="BTCUSDT",
        trade_id=1,
        price=Decimal("0"),
        quantity=Decimal("0"),
        event_time=now(),
        local_receive_time=now(),
    )

    result = validate_trade_event(event)

    assert isinstance(result, DataQualityResult)
    assert result.valid is False
    assert "price must be greater than zero." in result.errors
    assert "quantity must be greater than zero." in result.errors


def test_data_quality_result_returns_expected_order_book_errors() -> None:
    snapshot = OrderBookSnapshot.model_construct(
        symbol="BTCUSDT",
        last_update_id=1,
        bids=[],
        asks=[],
        event_time=now(),
        local_receive_time=now(),
    )

    result = validate_order_book_snapshot(snapshot)

    assert result.valid is False
    assert "Order book snapshot must include at least one bid." in result.errors
    assert "Order book snapshot must include at least one ask." in result.errors


def test_validate_order_book_delta_reports_invalid_update_range() -> None:
    delta = OrderBookDelta.model_construct(
        symbol="BTCUSDT",
        first_update_id=10,
        final_update_id=9,
        bids=[OrderBookLevel(price=Decimal("50000"), quantity=Decimal("0"))],
        asks=[],
        event_time=now(),
        local_receive_time=now(),
    )

    result = validate_order_book_delta(delta)

    assert result.valid is False
    assert "final_update_id must be greater than or equal to first_update_id." in result.errors


def test_validate_ohlcv_bar_reports_incoherent_range() -> None:
    bar = OHLCVBar.model_construct(
        symbol="BTCUSDT",
        interval="1m",
        open_time=now(),
        close_time=now(),
        open=Decimal("100"),
        high=Decimal("99"),
        low=Decimal("101"),
        close=Decimal("100"),
        volume=Decimal("-1"),
        event_time=now(),
        local_receive_time=now(),
    )

    result = validate_ohlcv_bar(bar)

    assert result.valid is False
    assert "close_time must be greater than open_time." in result.errors
    assert "high must be greater than or equal to open, close, and low." in result.errors
    assert "low must be less than or equal to open and close." in result.errors
    assert "volume must be greater than or equal to zero." in result.errors

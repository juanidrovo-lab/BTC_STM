from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from btc_stm.backtesting.data_feed import HistoricalDataFeed
from btc_stm.data.models import OHLCVBar


def make_bar(open_time: datetime, close: Decimal = Decimal("100")) -> OHLCVBar:
    close_time = open_time + timedelta(minutes=1)
    return OHLCVBar(
        symbol="BTCUSDT",
        interval="1m",
        open_time=open_time,
        close_time=close_time,
        open=Decimal("100"),
        high=max(Decimal("100"), close),
        low=min(Decimal("100"), close),
        close=close,
        volume=Decimal("1"),
        event_time=close_time,
        local_receive_time=close_time,
    )


def test_historical_data_feed_rejects_empty_bars() -> None:
    with pytest.raises(ValueError, match="at least one"):
        HistoricalDataFeed([])


def test_historical_data_feed_rejects_out_of_order_bars() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="chronological"):
        HistoricalDataFeed([make_bar(start + timedelta(minutes=1)), make_bar(start)])


def test_historical_data_feed_rejects_duplicate_open_time() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="duplicate"):
        HistoricalDataFeed([make_bar(start), make_bar(start)])


def test_historical_data_feed_iterates_in_order_and_exposes_bounds() -> None:
    start = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    bars = [make_bar(start), make_bar(start + timedelta(minutes=1))]
    feed = HistoricalDataFeed(bars)

    assert list(feed) == bars
    assert feed.first_timestamp == start
    assert feed.last_timestamp == start + timedelta(minutes=1)

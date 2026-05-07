"""In-memory historical OHLCV data feed."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from btc_stm.data.models import OHLCVBar


class HistoricalDataFeed:
    """Validates and iterates already-loaded historical bars."""

    def __init__(self, bars: list[OHLCVBar]) -> None:
        if not bars:
            raise ValueError("HistoricalDataFeed requires at least one bar.")
        previous_open_time: datetime | None = None
        seen_open_times: set[datetime] = set()
        for bar in bars:
            if bar.open_time in seen_open_times:
                raise ValueError("HistoricalDataFeed rejects duplicate open_time values.")
            if previous_open_time is not None and bar.open_time <= previous_open_time:
                raise ValueError("HistoricalDataFeed bars must be in chronological order.")
            seen_open_times.add(bar.open_time)
            previous_open_time = bar.open_time
        self._bars = list(bars)

    def __iter__(self) -> Iterator[OHLCVBar]:
        return iter(self._bars)

    @property
    def first_timestamp(self) -> datetime:
        return self._bars[0].open_time

    @property
    def last_timestamp(self) -> datetime:
        return self._bars[-1].open_time

    @property
    def bars(self) -> list[OHLCVBar]:
        return list(self._bars)

"""Safe Binance public market data client interface.

This module intentionally contains no API key handling, private endpoints, order
methods, or real network connection code. Production adapters can implement this
interface later behind explicit tests and configuration.
"""

from __future__ import annotations

from collections.abc import Iterator

from btc_stm.data.models import OHLCVBar, OrderBookDelta, OrderBookSnapshot, TradeEvent


class BinancePublicClient:
    """Mockable interface for Binance public market data only."""

    def get_order_book_snapshot(self, symbol: str) -> OrderBookSnapshot:
        raise NotImplementedError("Public REST adapter is not implemented.")

    def stream_trades(self, symbol: str) -> Iterator[TradeEvent]:
        raise NotImplementedError("Public trade stream adapter is not implemented.")

    def stream_order_book(self, symbol: str) -> Iterator[OrderBookDelta]:
        raise NotImplementedError("Public order book stream adapter is not implemented.")

    def stream_klines(self, symbol: str, interval: str) -> Iterator[OHLCVBar]:
        raise NotImplementedError("Public kline stream adapter is not implemented.")

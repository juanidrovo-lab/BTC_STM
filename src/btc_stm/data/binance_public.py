"""Safe Binance public market data client."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import httpx

from btc_stm.data.binance_parsers import parse_order_book_snapshot
from btc_stm.data.models import OHLCVBar, OrderBookDelta, OrderBookSnapshot, TradeEvent
from btc_stm.data.normalizer import normalize_symbol


class BinancePublicClient:
    """Public Binance Spot market data adapter.

    This client intentionally has no API key handling, signing, private endpoints,
    or order execution methods.
    """

    def __init__(
        self,
        *,
        base_url: str = "https://api.binance.com",
        timeout_seconds: float = 10.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client = http_client or httpx.Client(
            base_url=self.base_url,
            timeout=timeout_seconds,
        )

    def get_order_book_snapshot(self, symbol: str, limit: int = 100) -> OrderBookSnapshot:
        normalized_symbol = normalize_symbol(symbol)
        local_receive_time = datetime.now(UTC)
        response = self._client.get(
            "/api/v3/depth",
            params={"symbol": normalized_symbol, "limit": limit},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Binance depth response must be a JSON object.")
        event_time = datetime.now(UTC)
        return parse_order_book_snapshot(
            symbol=normalized_symbol,
            payload=payload,
            event_time=event_time,
            local_receive_time=local_receive_time,
        )

    def close(self) -> None:
        self._client.close()

    def stream_trades(self, symbol: str) -> Iterator[TradeEvent]:
        raise NotImplementedError("Public trade stream adapter is not implemented.")

    def stream_order_book(self, symbol: str) -> Iterator[OrderBookDelta]:
        raise NotImplementedError("Public order book stream adapter is not implemented.")

    def stream_klines(self, symbol: str, interval: str) -> Iterator[OHLCVBar]:
        raise NotImplementedError("Public kline stream adapter is not implemented.")

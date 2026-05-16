"""Safe Binance public market data client."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
import logging
import math

import httpx

logger = logging.getLogger("btc_stm.data.binance")

from btc_stm.data.binance_parsers import parse_order_book_snapshot
from btc_stm.data.models import OHLCVBar, OrderBookDelta, OrderBookSnapshot, TradeEvent
from btc_stm.data.normalizer import normalize_symbol

VALID_DEPTH_LIMITS = frozenset({5, 10, 20, 50, 100, 500, 1000, 5000})


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
        if not math.isfinite(timeout_seconds):
            raise ValueError("timeout_seconds must be finite.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client = http_client or httpx.Client(
            base_url=self.base_url,
            timeout=timeout_seconds,
        )

    def get_order_book_snapshot(self, symbol: str, limit: int = 100) -> OrderBookSnapshot:
        if limit not in VALID_DEPTH_LIMITS:
            raise ValueError("limit must be one of Binance's valid depth limits.")
        normalized_symbol = normalize_symbol(symbol)
        try:
            response = self._client.get(
                "/api/v3/depth",
                params={"symbol": normalized_symbol, "limit": limit},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "HTTP_ERROR | symbol=%s status=%s url=%s",
                normalized_symbol,
                exc.response.status_code,
                str(exc.request.url),
            )
            raise
        except httpx.RequestError as exc:
            logger.error("NETWORK_ERROR | symbol=%s | %s", normalized_symbol, exc)
            raise
        payload = response.json()
        receive_time = datetime.now(UTC)
        if not isinstance(payload, dict):
            logger.error("PARSE_ERROR | symbol=%s | depth response is not a JSON object", normalized_symbol)
            raise ValueError("Binance depth response must be a JSON object.")
        return parse_order_book_snapshot(
            symbol=normalized_symbol,
            payload=payload,
            event_time=receive_time,
            local_receive_time=receive_time,
        )

    def close(self) -> None:
        self._client.close()

    def stream_trades(self, symbol: str) -> Iterator[TradeEvent]:
        raise NotImplementedError("Public trade stream adapter is not implemented.")

    def stream_order_book(self, symbol: str) -> Iterator[OrderBookDelta]:
        raise NotImplementedError("Public order book stream adapter is not implemented.")

    def stream_klines(self, symbol: str, interval: str) -> Iterator[OHLCVBar]:
        raise NotImplementedError("Public kline stream adapter is not implemented.")

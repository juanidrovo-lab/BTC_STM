"""Async Binance WebSocket client with exponential-backoff reconnection.

Replaces the NotImplementedError stubs in BinancePublicClient with real
streaming connections to Binance's public WebSocket API.

Usage (async context)::

    async with BinanceWebSocketClient() as client:
        async for bar in client.stream_klines("BTCUSDT", "1m"):
            print(bar.close)

Each stream method is an async generator that reconnects automatically
when the connection drops.  The backoff starts at 1 s and doubles on
each failure, capped at 60 s.  A successful message resets the counter.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType

from btc_stm.data.binance_parsers import (
    parse_kline_event,
    parse_order_book_delta,
    parse_trade_event,
)
from btc_stm.data.models import OHLCVBar, OrderBookDelta, TradeEvent

logger = logging.getLogger("btc_stm.data.ws")

_WS_BASE = "wss://stream.binance.com:9443/ws"
_BACKOFF_INITIAL = 1.0
_BACKOFF_MAX = 60.0
_PING_INTERVAL = 20  # seconds — Binance drops silent connections after ~60 s


def _require_websockets() -> None:
    try:
        import websockets  # noqa: F401, PLC0415
    except ModuleNotFoundError as exc:
        raise ImportError(
            "websockets is not installed.  "
            "Install it with:  pip install websockets>=12"
        ) from exc


class BinanceWebSocketClient:
    """Async client for Binance public WebSocket streams.

    Designed for use as an async context manager::

        async with BinanceWebSocketClient() as client:
            async for bar in client.stream_klines("BTCUSDT", "1m"):
                ...

    Or directly::

        client = BinanceWebSocketClient()
        async for event in client.stream_trades("BTCUSDT"):
            ...
    """

    def __init__(self, base_url: str = _WS_BASE) -> None:
        _require_websockets()
        self._base_url = base_url.rstrip("/")

    async def __aenter__(self) -> "BinanceWebSocketClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        pass

    # ──────────────────────────────────────────────────────────────────────
    # Public async generators
    # ──────────────────────────────────────────────────────────────────────

    async def stream_klines(
        self,
        symbol: str,
        interval: str = "1m",
        *,
        closed_only: bool = True,
    ) -> AsyncIterator[OHLCVBar]:
        """Stream OHLCV bars from the Binance kline WebSocket.

        Parameters
        ----------
        symbol:
            Binance symbol, e.g. ``"BTCUSDT"``.
        interval:
            Kline interval string accepted by Binance: ``"1m"``, ``"5m"``,
            ``"1h"``, ``"1d"``, etc.
        closed_only:
            When ``True`` (default) only yields bars whose ``k.x`` flag is
            ``true`` (the candle is closed and final).  Set to ``False`` to
            receive every tick update.
        """
        stream = f"{symbol.lower()}@kline_{interval}"
        async for raw in self._stream(stream):
            try:
                receive_time = datetime.now(UTC)
                if not isinstance(raw, dict) or "k" not in raw:
                    continue
                if closed_only and not raw["k"].get("x", False):
                    continue
                yield parse_kline_event(
                    symbol=symbol.upper(),
                    payload=raw,
                    local_receive_time=receive_time,
                )
            except (ValueError, KeyError) as exc:
                logger.warning("KLINE_PARSE_ERROR | symbol=%s | %s", symbol, exc)
                continue

    async def stream_trades(self, symbol: str) -> AsyncIterator[TradeEvent]:
        """Stream individual trade events from the Binance trade WebSocket."""
        stream = f"{symbol.lower()}@trade"
        async for raw in self._stream(stream):
            try:
                receive_time = datetime.now(UTC)
                if not isinstance(raw, dict):
                    continue
                yield parse_trade_event(
                    symbol=symbol.upper(),
                    payload=raw,
                    local_receive_time=receive_time,
                )
            except (ValueError, KeyError) as exc:
                logger.warning("TRADE_PARSE_ERROR | symbol=%s | %s", symbol, exc)
                continue

    async def stream_order_book(
        self,
        symbol: str,
        depth: int = 20,
        speed_ms: int = 100,
    ) -> AsyncIterator[OrderBookDelta]:
        """Stream order-book diff events from the Binance depth WebSocket.

        Parameters
        ----------
        symbol:
            Binance symbol.
        depth:
            Partial book depth levels.  Binance accepts 5, 10, or 20.
        speed_ms:
            Update speed in milliseconds.  Binance accepts 100 or 1000.
        """
        if depth not in {5, 10, 20}:
            raise ValueError("depth must be 5, 10, or 20 for Binance partial book streams.")
        if speed_ms not in {100, 1000}:
            raise ValueError("speed_ms must be 100 or 1000 for Binance depth streams.")
        stream = f"{symbol.lower()}@depth{depth}@{speed_ms}ms"
        async for raw in self._stream(stream):
            try:
                receive_time = datetime.now(UTC)
                if not isinstance(raw, dict):
                    continue
                yield parse_order_book_delta(
                    symbol=symbol.upper(),
                    payload=raw,
                    local_receive_time=receive_time,
                )
            except (ValueError, KeyError) as exc:
                logger.warning("DEPTH_PARSE_ERROR | symbol=%s | %s", symbol, exc)
                continue

    # ──────────────────────────────────────────────────────────────────────
    # Internal reconnection loop
    # ──────────────────────────────────────────────────────────────────────

    async def _stream(self, stream_name: str) -> AsyncIterator[dict]:
        """Low-level async generator that yields parsed JSON dicts.

        Reconnects automatically on any network error using exponential
        backoff (1 s → 2 s → 4 s → … → 60 s max).  A successful message
        resets the backoff counter to 1 s.
        """
        import websockets  # noqa: PLC0415
        import websockets.exceptions  # noqa: PLC0415

        url = f"{self._base_url}/{stream_name}"
        backoff = _BACKOFF_INITIAL

        while True:
            try:
                logger.info("WS_CONNECT | stream=%s", stream_name)
                async with websockets.connect(
                    url,
                    ping_interval=_PING_INTERVAL,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    backoff = _BACKOFF_INITIAL  # reset on successful connect
                    async for message in ws:
                        try:
                            data = json.loads(message)
                        except json.JSONDecodeError as exc:
                            logger.warning("WS_JSON_ERROR | stream=%s | %s", stream_name, exc)
                            continue
                        backoff = _BACKOFF_INITIAL  # reset on every good message
                        yield data

            except (
                websockets.exceptions.ConnectionClosed,
                websockets.exceptions.WebSocketException,
                OSError,
                asyncio.TimeoutError,
            ) as exc:
                logger.warning(
                    "WS_DISCONNECTED | stream=%s | %s | reconnect_in=%.1fs",
                    stream_name,
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _BACKOFF_MAX)

            except asyncio.CancelledError:
                logger.info("WS_CANCELLED | stream=%s", stream_name)
                return

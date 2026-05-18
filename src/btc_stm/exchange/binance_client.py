"""Binance private REST client with HMAC-SHA256 request signing.

Handles only authenticated endpoints (orders, account, cancel).
Public market data should use the existing BinancePublicClient.
"""
from __future__ import annotations

import hashlib
import hmac
import time
import urllib.parse
from decimal import Decimal, ROUND_DOWN
from typing import Any

import httpx

BINANCE_MAINNET = "https://api.binance.com"
BINANCE_TESTNET = "https://testnet.binance.vision"


class BinanceAuthError(RuntimeError):
    """Raised when API credentials are missing or structurally invalid."""


class BinanceAPIError(RuntimeError):
    """Raised when Binance returns a negative error code."""

    def __init__(self, code: int, msg: str) -> None:
        super().__init__(f"Binance [{code}]: {msg}")
        self.code = code
        self.msg  = msg


class BinanceOrderClient:
    """Authenticated Binance Spot client.

    Instantiate via :func:`from_env` so credential validation is centralised.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        testnet: bool = True,
    ) -> None:
        if not api_key or not api_key.strip():
            raise BinanceAuthError("BINANCE_API_KEY is not set or empty.")
        if not api_secret or not api_secret.strip():
            raise BinanceAuthError("BINANCE_API_SECRET is not set or empty.")

        self._key    = api_key.strip()
        self._secret = api_secret.strip()
        self._base   = BINANCE_TESTNET if testnet else BINANCE_MAINNET
        self._http   = httpx.Client(
            base_url=self._base,
            headers={"X-MBX-APIKEY": self._key},
            timeout=10.0,
        )

    # ── Factory ─────────────────────────────────────────────────────────────

    @classmethod
    def from_env(cls, *, testnet: bool | None = None) -> "BinanceOrderClient":
        """Build client from environment variables.

        Raises BinanceAuthError immediately if credentials are absent,
        preventing any downstream 401 surprises.
        """
        import os  # noqa: PLC0415
        key    = os.environ.get("BINANCE_API_KEY",    "").strip()
        secret = os.environ.get("BINANCE_API_SECRET", "").strip()
        if not key or not secret:
            raise BinanceAuthError(
                "Both BINANCE_API_KEY and BINANCE_API_SECRET must be set in "
                "environment variables before using the live trading system."
            )
        use_testnet = (
            testnet
            if testnet is not None
            else os.environ.get("BINANCE_TESTNET", "true").lower() != "false"
        )
        return cls(key, secret, testnet=use_testnet)

    # ── Signing ──────────────────────────────────────────────────────────────

    def _sign(self, params: dict[str, Any]) -> dict[str, Any]:
        """Attach timestamp + HMAC-SHA256 signature in-place."""
        params["timestamp"] = int(time.time() * 1000)
        query_string        = urllib.parse.urlencode(params)
        signature = hmac.new(
            self._secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    # ── HTTP helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _raise_for_error(data: Any) -> None:
        if isinstance(data, dict) and isinstance(data.get("code"), int) and data["code"] < 0:
            raise BinanceAPIError(data["code"], data.get("msg", "unknown error"))

    def _get(self, path: str, params: dict | None = None, *, signed: bool = False) -> Any:
        p = dict(params or {})
        if signed:
            p = self._sign(p)
        r    = self._http.get(path, params=p)
        data = r.json()
        self._raise_for_error(data)
        return data

    def _post(self, path: str, params: dict | None = None) -> Any:
        p    = self._sign(dict(params or {}))
        r    = self._http.post(path, params=p)
        data = r.json()
        self._raise_for_error(data)
        return data

    def _delete(self, path: str, params: dict | None = None) -> Any:
        p    = self._sign(dict(params or {}))
        r    = self._http.delete(path, params=p)
        data = r.json()
        self._raise_for_error(data)
        return data

    # ── Public market data (no signature) ───────────────────────────────────

    def get_klines(self, symbol: str, interval: str, limit: int = 210) -> list[list]:
        """Raw kline rows: [openTime, open, high, low, close, volume, ...]"""
        return self._get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})

    def get_ticker_price(self, symbol: str) -> float:
        data = self._get("/api/v3/ticker/price", {"symbol": symbol})
        return float(data["price"])

    def get_exchange_info(self, symbol: str) -> dict:
        data = self._get("/api/v3/exchangeInfo", {"symbol": symbol})
        return next(s for s in data["symbols"] if s["symbol"] == symbol)

    # ── Account ──────────────────────────────────────────────────────────────

    def get_account(self) -> dict:
        return self._get("/api/v3/account", signed=True)

    def get_free_balance(self, asset: str) -> float:
        for a in self.get_account().get("balances", []):
            if a["asset"] == asset.upper():
                return float(a["free"])
        return 0.0

    def get_total_balance(self, asset: str) -> float:
        for a in self.get_account().get("balances", []):
            if a["asset"] == asset.upper():
                return float(a["free"]) + float(a["locked"])
        return 0.0

    # ── Order management ────────────────────────────────────────────────────

    def get_open_orders(self, symbol: str) -> list[dict]:
        return self._get("/api/v3/openOrders", {"symbol": symbol}, signed=True)

    def cancel_all_orders(self, symbol: str) -> list[dict]:
        """Cancel all open orders for symbol; returns list of cancelled orders."""
        return self._delete("/api/v3/openOrders", {"symbol": symbol})

    def place_limit_order(
        self,
        symbol:        str,
        side:          str,    # "BUY" | "SELL"
        quantity:      str,
        price:         str,
        time_in_force: str = "GTC",
    ) -> dict:
        return self._post("/api/v3/order", {
            "symbol":      symbol,
            "side":        side.upper(),
            "type":        "LIMIT",
            "quantity":    quantity,
            "price":       price,
            "timeInForce": time_in_force,
        })

    def place_market_order(self, symbol: str, side: str, quantity: str) -> dict:
        return self._post("/api/v3/order", {
            "symbol":   symbol,
            "side":     side.upper(),
            "type":     "MARKET",
            "quantity": quantity,
        })

    def place_oco_order(
        self,
        symbol:           str,
        side:             str,   # exit side (opposite of entry)
        quantity:         str,
        take_profit_price: str,  # limit leg — profit target
        stop_loss_price:  str,   # stop trigger
        stop_limit_price: str,   # stop execution price (slightly worse than trigger)
    ) -> dict:
        """Place an OCO (One-Cancels-the-Other) exit order covering TP and SL simultaneously."""
        return self._post("/api/v3/order/oco", {
            "symbol":                side and symbol,   # side is validated in caller
            "side":                  side.upper(),
            "quantity":              quantity,
            "price":                 take_profit_price,
            "stopPrice":             stop_loss_price,
            "stopLimitPrice":        stop_limit_price,
            "stopLimitTimeInForce":  "GTC",
        })

    # ── Lot size helper ──────────────────────────────────────────────────────

    def get_lot_size_filter(self, symbol: str) -> dict:
        info = self.get_exchange_info(symbol)
        return next(f for f in info["filters"] if f["filterType"] == "LOT_SIZE")

    def round_qty(self, symbol: str, raw_qty: Decimal) -> Decimal:
        """Round quantity down to the exchange's lot step size."""
        f    = self.get_lot_size_filter(symbol)
        step = Decimal(f["stepSize"])
        qty  = (raw_qty / step).to_integral_value(ROUND_DOWN) * step
        min_qty = Decimal(f["minQty"])
        if qty < min_qty:
            raise ValueError(
                f"Computed quantity {qty} < minQty {min_qty} for {symbol}. "
                "Increase balance or widen stop loss."
            )
        return qty

    def close(self) -> None:
        self._http.close()

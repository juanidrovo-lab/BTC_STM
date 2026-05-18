"""Live-trading risk policy enforcer.

Three hard-coded rules applied in sequence before any order touches Binance:

  1. EMA-200 trend filter  — no trades against the macro trend.
  2. 1% capital-at-risk    — position sized so the stop-loss costs ≤ 1% of
                             free USDT balance.
  3. Minimum 1:2 R:R ratio — take-profit must be at least 2× the stop distance.

All three must pass; a single failure raises ValueError with a clear reason.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from btc_stm.exchange.binance_client import BinanceOrderClient

# ── Hard-coded policy constants ──────────────────────────────────────────────
_MAX_RISK_PCT  = Decimal("0.01")   # 1 % of free USDT balance per trade
_MIN_RR        = Decimal("2.0")    # minimum reward : risk ratio
_EMA_PERIOD    = 200               # trend filter period (candles)
_EMA_INTERVAL  = "1h"             # timeframe used for trend determination
_SL_SLIPPAGE   = Decimal("0.001") # 0.1% buffer between stop-trigger and stop-limit


@dataclass(frozen=True)
class TradeSignal:
    """Caller-supplied intent.  All prices in quote currency (USDT)."""
    symbol:      str
    side:        str          # "BUY" | "SELL"
    entry:       Decimal
    stop_loss:   Decimal
    take_profit: Decimal


@dataclass(frozen=True)
class ValidatedOrder:
    """Fully validated order parameters ready to send to Binance."""
    symbol:            str
    side:              str
    quantity:          str    # formatted string for the API
    entry_price:       str
    stop_loss_price:   str
    stop_limit_price:  str    # slightly past stop for the OCO limit leg
    take_profit_price: str
    risk_usdt:         float
    rr_ratio:          float
    ema200:            float


# ── EMA helper ───────────────────────────────────────────────────────────────

def _ema(closes: list[float], period: int) -> float:
    """Standard exponential moving average seeded with SMA over first `period` bars."""
    if len(closes) < period + 1:
        raise ValueError(
            f"EMA-{period} requires at least {period + 1} closed candles; "
            f"got {len(closes)}."
        )
    k    = 2.0 / (period + 1)
    val  = sum(closes[:period]) / period   # SMA seed
    for price in closes[period:]:
        val = price * k + val * (1.0 - k)
    return val


# ── Price formatting helper ──────────────────────────────────────────────────

def _fmt(d: Decimal, tick: Decimal | None = None) -> str:
    """Format Decimal for Binance: round to tick if given, strip trailing zeros."""
    if tick and tick > 0:
        d = (d / tick).to_integral_value(ROUND_DOWN) * tick
    s = f"{d:.8f}".rstrip("0").rstrip(".")
    return s


# ── TradeGuard ───────────────────────────────────────────────────────────────

class TradeGuard:
    """Validates a TradeSignal against all three live-trading risk rules.

    Usage::

        guard  = TradeGuard(client)
        order  = guard.validate(signal)   # raises ValueError on any breach
        # … then send order to Binance
    """

    def __init__(self, client: "BinanceOrderClient") -> None:
        self._client = client

    # ── Rule 1: EMA-200 trend filter ────────────────────────────────────────

    def _check_trend(self, symbol: str, side: str) -> float:
        """Returns EMA-200 value if trade is trend-aligned, else raises."""
        klines  = self._client.get_klines(symbol, _EMA_INTERVAL, limit=_EMA_PERIOD + 10)
        # Use fully-closed candles only (exclude the last incomplete bar)
        closes  = [float(k[4]) for k in klines[:-1]]
        current = float(klines[-1][4])
        ema200  = _ema(closes, _EMA_PERIOD)

        aligned = (
            (side.upper() == "BUY"  and current > ema200) or
            (side.upper() == "SELL" and current < ema200)
        )
        if not aligned:
            direction = "above" if side.upper() == "BUY" else "below"
            raise ValueError(
                f"Trend filter BLOCKED: {side.upper()} requires price {direction} "
                f"EMA-{_EMA_PERIOD}. "
                f"Current={current:.2f}, EMA200={ema200:.2f}. "
                "No counter-trend entries allowed."
            )
        return ema200

    # ── Rule 2: 1% position sizing ───────────────────────────────────────────

    def _size_position(self, symbol: str, entry: Decimal, stop_loss: Decimal) -> tuple[Decimal, float]:
        """Returns (quantity, risk_usdt). Quantity sized so SL costs exactly 1% of free balance."""
        balance_f = self._client.get_free_balance("USDT")
        if balance_f < 10.0:
            raise ValueError(
                f"Insufficient free USDT balance: ${balance_f:.2f}. "
                "Minimum $10 required."
            )
        balance   = Decimal(str(balance_f))
        risk_usdt = balance * _MAX_RISK_PCT
        sl_dist   = abs(entry - stop_loss)

        if sl_dist == 0:
            raise ValueError("entry and stop_loss cannot be equal — stop distance is zero.")

        raw_qty = risk_usdt / sl_dist
        qty     = self._client.round_qty(symbol, raw_qty)
        return qty, float(risk_usdt)

    # ── Rule 3: R:R ratio check ──────────────────────────────────────────────

    @staticmethod
    def _check_rr(entry: Decimal, stop_loss: Decimal, take_profit: Decimal) -> float:
        sl_dist = abs(entry - stop_loss)
        tp_dist = abs(take_profit - entry)
        if sl_dist == 0:
            raise ValueError("Cannot compute R:R — stop distance is zero.")
        rr = tp_dist / sl_dist
        if rr < _MIN_RR:
            raise ValueError(
                f"R:R {float(rr):.2f} is below the minimum {float(_MIN_RR):.1f}. "
                f"Move take-profit further or tighten the stop-loss."
            )
        return float(rr)

    # ── Master validator ─────────────────────────────────────────────────────

    def validate(self, signal: TradeSignal) -> ValidatedOrder:
        """Run all three rules. Returns ValidatedOrder or raises ValueError."""
        side = signal.side.upper()
        if side not in ("BUY", "SELL"):
            raise ValueError(f"side must be BUY or SELL, got: {signal.side!r}")

        # 1. Trend filter
        ema200 = self._check_trend(signal.symbol, side)

        # 2. R:R ratio (cheap check before fetching account balance)
        rr = self._check_rr(signal.entry, signal.stop_loss, signal.take_profit)

        # 3. Position sizing (requires API call to fetch balance)
        qty, risk_usdt = self._size_position(signal.symbol, signal.entry, signal.stop_loss)

        # Compute stop-limit price (slightly beyond stop-trigger to avoid missed fills)
        if side == "BUY":
            # Stop-loss on a long is a SELL; limit leg is slightly below trigger
            stop_limit = signal.stop_loss * (Decimal("1") - _SL_SLIPPAGE)
        else:
            # Stop-loss on a short is a BUY; limit leg is slightly above trigger
            stop_limit = signal.stop_loss * (Decimal("1") + _SL_SLIPPAGE)

        return ValidatedOrder(
            symbol            = signal.symbol,
            side              = side,
            quantity          = _fmt(qty),
            entry_price       = _fmt(signal.entry),
            stop_loss_price   = _fmt(signal.stop_loss),
            stop_limit_price  = _fmt(stop_limit),
            take_profit_price = _fmt(signal.take_profit),
            risk_usdt         = risk_usdt,
            rr_ratio          = rr,
            ema200            = ema200,
        )

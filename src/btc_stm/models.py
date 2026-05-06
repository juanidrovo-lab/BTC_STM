from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class SignalAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


@dataclass(frozen=True)
class Signal:
    action: SignalAction
    strength: Decimal


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: Decimal
    quantity: Decimal
    stop_loss_price: Decimal | None = None


@dataclass(frozen=True)
class PortfolioState:
    cash_balance: Decimal
    position_size: Decimal


@dataclass(frozen=True)
class SymbolFilters:
    min_price: Decimal
    max_price: Decimal
    tick_size: Decimal
    min_qty: Decimal
    max_qty: Decimal
    step_size: Decimal
    min_notional: Decimal


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str | None = None

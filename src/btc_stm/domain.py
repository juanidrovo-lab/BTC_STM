from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: Decimal
    entry_price: Decimal


@dataclass(frozen=True)
class BinanceSymbolFilters:
    min_qty: Decimal
    max_qty: Decimal
    step_size: Decimal
    min_price: Decimal
    max_price: Decimal
    tick_size: Decimal
    min_notional: Decimal

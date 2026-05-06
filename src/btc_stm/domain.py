from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    quantity: float
    price: float


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: float
    entry_price: float

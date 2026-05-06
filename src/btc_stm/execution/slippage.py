"""Slippage calculations for paper execution."""

from __future__ import annotations

from decimal import Decimal

from btc_stm.domain import OrderSide


def apply_slippage(price: Decimal, side: OrderSide, slippage_bps: Decimal) -> Decimal:
    if price <= 0:
        raise ValueError("price must be greater than zero")
    if slippage_bps < 0:
        raise ValueError("slippage_bps must be greater than or equal to zero")

    multiplier = slippage_bps / Decimal("10000")
    if side is OrderSide.BUY:
        return price * (Decimal("1") + multiplier)
    return price * (Decimal("1") - multiplier)

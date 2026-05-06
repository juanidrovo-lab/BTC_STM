"""Slippage calculations for paper execution."""

from __future__ import annotations

from decimal import Decimal

from btc_stm.domain import OrderSide


def apply_slippage(price: Decimal, side: OrderSide, slippage_bps: Decimal) -> Decimal:
    if not price.is_finite():
        raise ValueError("price must be a finite decimal")
    if not slippage_bps.is_finite():
        raise ValueError("slippage_bps must be a finite decimal")
    if price <= 0:
        raise ValueError("price must be greater than zero")
    if slippage_bps < 0:
        raise ValueError("slippage_bps must be greater than or equal to zero")

    multiplier = slippage_bps / Decimal("10000")
    if side is OrderSide.BUY:
        final_price = price * (Decimal("1") + multiplier)
    else:
        final_price = price * (Decimal("1") - multiplier)
    if final_price <= 0:
        raise ValueError("slippage produced a non-positive final price")
    return final_price

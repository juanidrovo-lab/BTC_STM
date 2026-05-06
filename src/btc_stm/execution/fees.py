"""Fee calculations for paper execution."""

from __future__ import annotations

from decimal import Decimal


def calculate_fee(notional: Decimal, fee_rate_bps: Decimal) -> Decimal:
    if not notional.is_finite():
        raise ValueError("notional must be a finite decimal")
    if not fee_rate_bps.is_finite():
        raise ValueError("fee_rate_bps must be a finite decimal")
    if notional < 0:
        raise ValueError("notional must be greater than or equal to zero")
    if fee_rate_bps < 0:
        raise ValueError("fee_rate_bps must be greater than or equal to zero")
    return notional * fee_rate_bps / Decimal("10000")

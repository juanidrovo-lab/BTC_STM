from __future__ import annotations

from decimal import Decimal

from btc_stm.models import OrderIntent, RiskDecision, SymbolFilters


class RiskManager:
    """Centralized risk and filter validation for paper trading."""

    def __init__(self, trading_mode: str = "paper", enable_live_trading: bool = False) -> None:
        self.trading_mode = trading_mode
        self.enable_live_trading = enable_live_trading

    @staticmethod
    def _is_tick_aligned(value: Decimal, minimum: Decimal, step: Decimal) -> bool:
        if step <= 0:
            return False
        return (value - minimum) % step == 0

    @staticmethod
    def _all_finite(values: list[Decimal | None]) -> bool:
        return all(v is None or v.is_finite() for v in values)

    def evaluate(self, intent: OrderIntent, filters: SymbolFilters) -> RiskDecision:
        critical_values: list[Decimal | None] = [
            intent.price,
            intent.quantity,
            intent.stop_loss_price,
            filters.min_price,
            filters.max_price,
            filters.tick_size,
            filters.min_qty,
            filters.max_qty,
            filters.step_size,
            filters.min_notional,
        ]
        if not self._all_finite(critical_values):
            return RiskDecision(approved=False, reason="Non-finite numeric value detected")

        if self.trading_mode != "paper" or self.enable_live_trading:
            return RiskDecision(approved=False, reason="Live trading is blocked by default")

        if not (filters.min_price <= intent.price <= filters.max_price):
            return RiskDecision(approved=False, reason="Price out of bounds")
        if not self._is_tick_aligned(intent.price, filters.min_price, filters.tick_size):
            return RiskDecision(approved=False, reason="PRICE_FILTER tick alignment violation")

        if not (filters.min_qty <= intent.quantity <= filters.max_qty):
            return RiskDecision(approved=False, reason="Quantity out of bounds")
        if not self._is_tick_aligned(intent.quantity, filters.min_qty, filters.step_size):
            return RiskDecision(approved=False, reason="LOT_SIZE step alignment violation")

        if intent.price * intent.quantity < filters.min_notional:
            return RiskDecision(approved=False, reason="MIN_NOTIONAL violation")

        if intent.stop_loss_price is not None and intent.stop_loss_price <= 0:
            return RiskDecision(approved=False, reason="Invalid stop loss")

        return RiskDecision(approved=True)

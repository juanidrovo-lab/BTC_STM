"""Centralized risk manager for paper mode."""

from __future__ import annotations

from decimal import Decimal

from btc_stm.domain import OrderIntent, PortfolioState, RiskDecision, SymbolFilters
from btc_stm.settings import Settings


class RiskManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate(
        self,
        *,
        order: OrderIntent,
        portfolio: PortfolioState,
        filters: SymbolFilters,
    ) -> RiskDecision:
        reasons: list[str] = []

        if self.settings.risk_kill_switch:
            reasons.append("Kill switch is enabled.")

        if order.stop_loss is None:
            reasons.append("Order rejected: stop-loss is mandatory.")

        daily_loss_pct = Decimal("0")
        if portfolio.daily_pnl < 0:
            daily_loss_pct = (abs(portfolio.daily_pnl) / portfolio.equity) * Decimal("100")
        if daily_loss_pct > Decimal(str(self.settings.risk_max_daily_loss_pct)):
            reasons.append("Order rejected: max daily loss exceeded.")

        if portfolio.open_positions >= self.settings.risk_max_open_positions:
            reasons.append("Order rejected: max open positions reached.")

        position_notional = order.price * order.quantity
        if position_notional > Decimal(str(self.settings.risk_max_position_notional)):
            reasons.append("Order rejected: max position notional exceeded.")

        max_risk_cash = portfolio.equity * Decimal(str(self.settings.risk_max_risk_per_trade_pct)) / Decimal("100")
        if order.stop_loss is not None:
            per_unit_risk = abs(order.price - order.stop_loss)
            trade_risk = per_unit_risk * order.quantity
            if trade_risk > max_risk_cash:
                reasons.append("Order rejected: max risk per trade exceeded.")

        self._validate_price_filter(order, filters, reasons)
        self._validate_lot_size(order, filters, reasons)
        self._validate_min_notional(position_notional, filters, reasons)

        return RiskDecision(approved=len(reasons) == 0, reasons=reasons)

    @staticmethod
    def _is_multiple(value: Decimal, step: Decimal) -> bool:
        return (value % step) == 0

    def _validate_price_filter(
        self, order: OrderIntent, filters: SymbolFilters, reasons: list[str]
    ) -> None:
        if not (filters.price_min <= order.price <= filters.price_max):
            reasons.append("Order rejected: PRICE_FILTER range violation.")
            return
        if not self._is_multiple(order.price, filters.price_tick_size):
            reasons.append("Order rejected: PRICE_FILTER tick size violation.")

    def _validate_lot_size(
        self, order: OrderIntent, filters: SymbolFilters, reasons: list[str]
    ) -> None:
        if not (filters.qty_min <= order.quantity <= filters.qty_max):
            reasons.append("Order rejected: LOT_SIZE range violation.")
            return
        if not self._is_multiple(order.quantity, filters.qty_step_size):
            reasons.append("Order rejected: LOT_SIZE step size violation.")

    @staticmethod
    def _validate_min_notional(
        notional: Decimal, filters: SymbolFilters, reasons: list[str]
    ) -> None:
        if notional < filters.min_notional:
            reasons.append("Order rejected: MIN_NOTIONAL violation.")

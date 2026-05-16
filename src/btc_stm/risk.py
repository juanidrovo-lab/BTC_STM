"""Centralized risk manager for paper mode."""

from __future__ import annotations

import logging
from decimal import Decimal

from btc_stm.domain import OrderIntent, OrderSide, PortfolioState, RiskDecision, SymbolFilters
from btc_stm.settings import Settings

logger = logging.getLogger("btc_stm.risk")


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

        if not self._all_finite(
            [
                order.quantity,
                order.price,
                order.stop_loss,
                order.take_profit,
                portfolio.equity,
                portfolio.daily_pnl,
                filters.price_min,
                filters.price_max,
                filters.price_tick_size,
                filters.qty_min,
                filters.qty_max,
                filters.qty_step_size,
                filters.min_notional,
            ]
        ):
            return RiskDecision(
                approved=False,
                reasons=["Order rejected: non-finite numeric value detected."],
            )

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

        max_risk_cash = (
            portfolio.equity
            * Decimal(str(self.settings.risk_max_risk_per_trade_pct))
            / Decimal("100")
        )
        if order.stop_loss is not None:
            per_unit_risk = abs(order.price - order.stop_loss)
            trade_risk = per_unit_risk * order.quantity
            if trade_risk > max_risk_cash:
                reasons.append("Order rejected: max risk per trade exceeded.")

        self._validate_price_filter(order, filters, reasons)
        self._validate_lot_size(order, filters, reasons)
        self._validate_min_notional(position_notional, filters, reasons)
        self._validate_take_profit(order, reasons)

        if reasons:
            for reason in reasons:
                logger.warning(
                    "RISK_REJECTED | symbol=%s side=%s price=%s qty=%s | %s",
                    order.symbol,
                    order.side.value,
                    order.price,
                    order.quantity,
                    reason,
                )

        return RiskDecision(approved=len(reasons) == 0, reasons=reasons)

    @staticmethod
    def _all_finite(values: list[Decimal | None]) -> bool:
        return all(value is None or value.is_finite() for value in values)

    @staticmethod
    def _is_aligned_to_minimum(value: Decimal, minimum: Decimal, step: Decimal) -> bool:
        if step <= 0:
            return False
        return (value - minimum) % step == 0

    def _validate_price_filter(
        self, order: OrderIntent, filters: SymbolFilters, reasons: list[str]
    ) -> None:
        if not (filters.price_min <= order.price <= filters.price_max):
            reasons.append("Order rejected: PRICE_FILTER range violation.")
            return
        if not self._is_aligned_to_minimum(
            order.price,
            filters.price_min,
            filters.price_tick_size,
        ):
            reasons.append("Order rejected: PRICE_FILTER tick size violation.")

    def _validate_lot_size(
        self, order: OrderIntent, filters: SymbolFilters, reasons: list[str]
    ) -> None:
        if not (filters.qty_min <= order.quantity <= filters.qty_max):
            reasons.append("Order rejected: LOT_SIZE range violation.")
            return
        if not self._is_aligned_to_minimum(
            order.quantity,
            filters.qty_min,
            filters.qty_step_size,
        ):
            reasons.append("Order rejected: LOT_SIZE step size violation.")

    @staticmethod
    def _validate_min_notional(
        notional: Decimal, filters: SymbolFilters, reasons: list[str]
    ) -> None:
        if notional < filters.min_notional:
            reasons.append("Order rejected: MIN_NOTIONAL violation.")

    @staticmethod
    def _validate_take_profit(order: OrderIntent, reasons: list[str]) -> None:
        if order.take_profit is None:
            return
        if order.side == OrderSide.BUY and order.take_profit <= order.price:
            reasons.append(
                "Order rejected: BUY take_profit must be above entry price."
            )
        elif order.side == OrderSide.SELL and order.take_profit >= order.price:
            reasons.append(
                "Order rejected: SELL take_profit must be below entry price."
            )

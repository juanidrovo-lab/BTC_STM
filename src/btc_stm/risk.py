from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from btc_stm.domain import BinanceSymbolFilters
from btc_stm.settings import Settings


@dataclass
class RiskManager:
    max_order_notional: Decimal = Decimal("5000")

    def enforce_live_trading_guard(self, settings: Settings) -> None:
        settings.validate_live_trading_safety()

    @staticmethod
    def _is_multiple(value: Decimal, step: Decimal) -> bool:
        return (value % step) == Decimal("0")

    def validate_order(
        self,
        *,
        quantity: Decimal,
        price: Decimal,
        filters: BinanceSymbolFilters,
    ) -> None:
        if quantity <= 0:
            raise ValueError("Order quantity must be positive.")
        if price <= 0:
            raise ValueError("Order price must be positive.")

        if quantity < filters.min_qty or quantity > filters.max_qty:
            raise ValueError("Order quantity outside Binance LOT_SIZE bounds.")
        if not self._is_multiple(quantity, filters.step_size):
            raise ValueError("Order quantity does not match Binance LOT_SIZE step size.")

        if price < filters.min_price or price > filters.max_price:
            raise ValueError("Order price outside Binance PRICE_FILTER bounds.")
        if not self._is_multiple(price, filters.tick_size):
            raise ValueError("Order price does not match Binance PRICE_FILTER tick size.")

        notional = quantity * price
        if notional < filters.min_notional:
            raise ValueError("Order notional below Binance MIN_NOTIONAL.")
        if notional > self.max_order_notional:
            raise ValueError(
                f"Order notional {notional} exceeds max allowed {self.max_order_notional}."
            )

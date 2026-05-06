from __future__ import annotations

from dataclasses import dataclass

from btc_stm.settings import Settings


@dataclass
class RiskManager:
    max_order_notional: float = 5_000.0

    def enforce_live_trading_guard(self, settings: Settings) -> None:
        settings.validate_live_trading_safety()

    def validate_order(self, quantity: float, price: float) -> None:
        if quantity <= 0:
            raise ValueError("Order quantity must be positive.")
        if price <= 0:
            raise ValueError("Order price must be positive.")

        notional = quantity * price
        if notional > self.max_order_notional:
            raise ValueError(
                f"Order notional {notional:.2f} exceeds max allowed {self.max_order_notional:.2f}."
            )

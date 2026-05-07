"""Simple deterministic example strategies."""

from __future__ import annotations

from decimal import Decimal

from btc_stm.domain import OrderIntent, OrderSide, OrderType
from btc_stm.strategy.models import StrategyContext, StrategyDecision, normalize_strategy_symbol


class NoOpStrategy:
    name = "noop"

    def on_bar(self, context: StrategyContext) -> StrategyDecision:
        return StrategyDecision(
            strategy_name=self.name,
            timestamp=context.current_bar.open_time,
            orders=[],
            reason="No action.",
        )


class OneShotBuyStrategy:
    name = "one_shot_buy"

    def __init__(self, *, symbol: str, quantity: Decimal, stop_loss_pct: Decimal) -> None:
        if not quantity.is_finite() or quantity <= 0:
            raise ValueError("quantity must be a positive finite Decimal.")
        if not stop_loss_pct.is_finite() or stop_loss_pct <= 0 or stop_loss_pct >= 100:
            raise ValueError("stop_loss_pct must be greater than 0 and less than 100.")
        self.symbol = normalize_strategy_symbol(symbol)
        self.quantity = quantity
        self.stop_loss_pct = stop_loss_pct
        self._has_bought = False

    def on_bar(self, context: StrategyContext) -> StrategyDecision:
        if self._has_bought:
            return StrategyDecision(
                strategy_name=self.name,
                timestamp=context.current_bar.open_time,
                orders=[],
                reason="Already bought.",
            )
        if context.symbol != self.symbol:
            raise ValueError("Strategy context symbol must match strategy symbol.")

        reference_price = context.current_bar.close
        stop_loss = reference_price * (Decimal("1") - self.stop_loss_pct / Decimal("100"))
        self._has_bought = True
        return StrategyDecision(
            strategy_name=self.name,
            timestamp=context.current_bar.open_time,
            orders=[
                OrderIntent(
                    symbol=self.symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.LIMIT,
                    quantity=self.quantity,
                    price=reference_price,
                    stop_loss=stop_loss,
                )
            ],
            reason="One-shot deterministic buy.",
        )

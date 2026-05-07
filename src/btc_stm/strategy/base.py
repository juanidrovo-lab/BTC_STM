"""Base strategy protocol."""

from __future__ import annotations

from typing import Protocol

from btc_stm.strategy.models import StrategyContext, StrategyDecision


class Strategy(Protocol):
    name: str

    def on_bar(self, context: StrategyContext) -> StrategyDecision:
        """Generate order intentions from visible historical context only."""
        ...

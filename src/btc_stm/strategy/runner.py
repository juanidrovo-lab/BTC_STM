"""Strategy runner that converts decisions into scheduled paper orders."""

from __future__ import annotations

from btc_stm.backtesting.data_feed import HistoricalDataFeed
from btc_stm.backtesting.models import ScheduledOrder
from btc_stm.data.models import OHLCVBar
from btc_stm.strategy.base import Strategy
from btc_stm.strategy.models import (
    StrategyContext,
    StrategyDecision,
    StrategyRunResult,
    normalize_strategy_symbol,
)


class StrategyRunner:
    def __init__(self, *, strategy: Strategy, symbol: str) -> None:
        self.strategy = strategy
        self.symbol = normalize_strategy_symbol(symbol)

    def run(self, bars: list[OHLCVBar] | HistoricalDataFeed) -> StrategyRunResult:
        ordered_bars = bars.bars if isinstance(bars, HistoricalDataFeed) else list(bars)
        data_feed = HistoricalDataFeed(ordered_bars)
        history: list[OHLCVBar] = []
        decisions: list[StrategyDecision] = []
        scheduled_orders: list[ScheduledOrder] = []

        for bar in data_feed:
            history.append(bar)
            context = StrategyContext(
                symbol=self.symbol,
                current_bar=bar,
                history=list(history),
            )
            decision = self.strategy.on_bar(context)
            self._validate_decision(decision)
            decisions.append(decision)
            for order in decision.orders:
                scheduled_orders.append(
                    ScheduledOrder(execute_at=bar.open_time, order=order)
                )

        return StrategyRunResult(
            strategy_name=self.strategy.name,
            scheduled_orders=scheduled_orders,
            decisions=decisions,
        )

    def _validate_decision(self, decision: StrategyDecision) -> None:
        for order in decision.orders:
            if order.symbol != self.symbol:
                raise ValueError("Strategy order symbol must match runner symbol.")
            if order.stop_loss is None:
                raise ValueError("Strategy order must include stop_loss.")

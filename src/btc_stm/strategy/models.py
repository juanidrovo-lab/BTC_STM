"""Models for deterministic strategy decisions."""

from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from btc_stm.backtesting.models import ScheduledOrder
from btc_stm.data.models import OHLCVBar
from btc_stm.domain import OrderIntent
from btc_stm.execution.models import PaperPortfolio


def normalize_strategy_symbol(value: str) -> str:
    return value.upper().strip().replace("/", "").replace("-", "")


class StrategyContext(BaseModel):
    """Context visible to a strategy for one bar.

    Policy: history may include the current bar, but never bars with open_time
    greater than current_bar.open_time.
    """

    symbol: str
    current_bar: OHLCVBar
    history: list[OHLCVBar]
    portfolio: PaperPortfolio | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return normalize_strategy_symbol(value)

    @model_validator(mode="after")
    def validate_context(self) -> Self:
        if self.current_bar.symbol != self.symbol:
            raise ValueError("current_bar symbol must match strategy symbol.")
        seen_open_times: set[datetime] = set()
        for bar in self.history:
            if bar.symbol != self.symbol:
                raise ValueError("history bar symbol must match strategy symbol.")
            if bar.open_time > self.current_bar.open_time:
                raise ValueError("history must not include future bars.")
            if bar.open_time in seen_open_times:
                raise ValueError("history must not include duplicate open_time values.")
            seen_open_times.add(bar.open_time)
        return self


class StrategyDecision(BaseModel):
    strategy_name: str
    timestamp: datetime
    orders: list[OrderIntent] = Field(default_factory=list)
    reason: str | None = None

    @field_validator("strategy_name")
    @classmethod
    def validate_strategy_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("strategy_name must not be empty.")
        return value

    @model_validator(mode="after")
    def validate_orders(self) -> Self:
        for order in self.orders:
            if order.stop_loss is None:
                raise ValueError("strategy orders must include stop_loss.")
        return self


class StrategyRunResult(BaseModel):
    strategy_name: str
    scheduled_orders: list[ScheduledOrder]
    decisions: list[StrategyDecision]

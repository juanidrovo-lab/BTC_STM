"""Models for deterministic paper trading orchestration."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from btc_stm.analytics.models import PerformanceReport
from btc_stm.backtesting.models import EquityPoint
from btc_stm.execution.models import ExecutionReport
from btc_stm.strategy.models import StrategyDecision, normalize_strategy_symbol


class OrchestratorEventType(StrEnum):
    BAR_RECEIVED = "bar_received"
    STRATEGY_DECISION = "strategy_decision"
    ORDER_SCHEDULED = "order_scheduled"
    ORDER_EXECUTED = "order_executed"
    ORDER_REJECTED = "order_rejected"
    EQUITY_UPDATED = "equity_updated"
    SESSION_COMPLETED = "session_completed"
    SESSION_FAILED = "session_failed"


class OrchestratorEvent(BaseModel):
    event_type: OrchestratorEventType
    timestamp: datetime
    message: str
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be empty.")
        return value


class PaperTradingConfig(BaseModel):
    symbol: str
    initial_cash: Decimal = Field(gt=Decimal("0"))
    fee_rate_bps: Decimal = Field(ge=Decimal("0"))
    slippage_bps: Decimal = Field(ge=Decimal("0"))
    execute_on: str = "close"

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return normalize_strategy_symbol(value)

    @field_validator("execute_on")
    @classmethod
    def validate_execute_on(cls, value: str) -> str:
        if value not in {"open", "close"}:
            raise ValueError("execute_on must be either 'open' or 'close'.")
        return value

    @model_validator(mode="after")
    def validate_finite_decimals(self) -> Self:
        values = [self.initial_cash, self.fee_rate_bps, self.slippage_bps]
        if not all(value.is_finite() for value in values):
            raise ValueError("PaperTradingConfig numeric values must be finite.")
        return self


class PaperTradingSessionResult(BaseModel):
    config: PaperTradingConfig
    decisions: list[StrategyDecision]
    execution_reports: list[ExecutionReport]
    equity_curve: list[EquityPoint]
    performance_report: PerformanceReport
    events: list[OrchestratorEvent]

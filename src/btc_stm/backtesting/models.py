"""Backtesting models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from btc_stm.domain import OrderIntent
from btc_stm.execution.models import ExecutionReport


class BacktestConfig(BaseModel):
    symbol: str
    initial_cash: Decimal = Field(gt=Decimal("0"))
    fee_rate_bps: Decimal = Field(ge=Decimal("0"))
    slippage_bps: Decimal = Field(ge=Decimal("0"))
    execute_on: str = "close"

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper().strip().replace("/", "").replace("-", "")

    @field_validator("execute_on")
    @classmethod
    def validate_execute_on(cls, value: str) -> str:
        if value not in {"open", "close"}:
            raise ValueError("execute_on must be either 'open' or 'close'")
        return value

    @model_validator(mode="after")
    def validate_finite_decimals(self) -> Self:
        values = [self.initial_cash, self.fee_rate_bps, self.slippage_bps]
        if not all(value.is_finite() for value in values):
            raise ValueError("BacktestConfig numeric values must be finite.")
        return self


class ScheduledOrder(BaseModel):
    execute_at: datetime
    order: OrderIntent


class EquityPoint(BaseModel):
    timestamp: datetime
    equity: Decimal = Field(ge=Decimal("0"))
    cash_balance: Decimal = Field(ge=Decimal("0"))
    position_value: Decimal = Field(ge=Decimal("0"))
    realized_pnl: Decimal

    @model_validator(mode="after")
    def validate_finite_decimals(self) -> Self:
        values = [self.equity, self.cash_balance, self.position_value, self.realized_pnl]
        if not all(value.is_finite() for value in values):
            raise ValueError("EquityPoint numeric values must be finite.")
        return self


class BacktestTrade(BaseModel):
    timestamp: datetime
    execution_report: ExecutionReport


class BacktestMetrics(BaseModel):
    starting_equity: Decimal
    ending_equity: Decimal
    total_return_pct: Decimal
    max_drawdown_pct: Decimal
    total_trades: int = Field(ge=0)
    winning_trades: int = Field(ge=0)
    losing_trades: int = Field(ge=0)
    total_fees_paid: Decimal = Field(ge=Decimal("0"))

    @model_validator(mode="after")
    def validate_finite_decimals(self) -> Self:
        values = [
            self.starting_equity,
            self.ending_equity,
            self.total_return_pct,
            self.max_drawdown_pct,
            self.total_fees_paid,
        ]
        if not all(value.is_finite() for value in values):
            raise ValueError("BacktestMetrics numeric values must be finite.")
        return self


class BacktestResult(BaseModel):
    config: BacktestConfig
    trades: list[BacktestTrade]
    equity_curve: list[EquityPoint]
    metrics: BacktestMetrics

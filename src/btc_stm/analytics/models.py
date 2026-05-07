"""Analytics result models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, model_validator


class ReturnPoint(BaseModel):
    timestamp: datetime
    equity: Decimal = Field(ge=Decimal("0"))
    period_return_pct: Decimal

    @model_validator(mode="after")
    def validate_finite_decimals(self) -> Self:
        _validate_finite_decimals([self.equity, self.period_return_pct])
        return self


class DrawdownPoint(BaseModel):
    timestamp: datetime
    equity: Decimal = Field(ge=Decimal("0"))
    peak_equity: Decimal = Field(ge=Decimal("0"))
    drawdown_pct: Decimal = Field(ge=Decimal("0"))

    @model_validator(mode="after")
    def validate_finite_decimals(self) -> Self:
        _validate_finite_decimals([self.equity, self.peak_equity, self.drawdown_pct])
        return self


class EquityCurveAnalysis(BaseModel):
    starting_equity: Decimal
    ending_equity: Decimal
    total_return_pct: Decimal
    max_drawdown_pct: Decimal
    max_drawdown_start: datetime | None
    max_drawdown_end: datetime | None
    return_points: list[ReturnPoint]
    drawdown_points: list[DrawdownPoint]

    @model_validator(mode="after")
    def validate_finite_decimals(self) -> Self:
        _validate_finite_decimals(
            [
                self.starting_equity,
                self.ending_equity,
                self.total_return_pct,
                self.max_drawdown_pct,
            ]
        )
        return self


class TradeAnalytics(BaseModel):
    total_reports: int = Field(ge=0)
    filled_reports: int = Field(ge=0)
    rejected_reports: int = Field(ge=0)
    partially_filled_reports: int = Field(ge=0)
    total_notional: Decimal = Field(ge=Decimal("0"))
    total_fees: Decimal = Field(ge=Decimal("0"))
    average_fill_price: Decimal | None = None

    @model_validator(mode="after")
    def validate_finite_decimals(self) -> Self:
        values = [self.total_notional, self.total_fees]
        if self.average_fill_price is not None:
            values.append(self.average_fill_price)
        _validate_finite_decimals(values)
        return self


class PerformanceReport(BaseModel):
    equity: EquityCurveAnalysis
    trades: TradeAnalytics
    warnings: list[str] = Field(default_factory=list)


def _validate_finite_decimals(values: list[Decimal]) -> None:
    if not all(value.is_finite() for value in values):
        raise ValueError("Analytics Decimal values must be finite.")

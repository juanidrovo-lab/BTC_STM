"""Domain models for Sprint 0."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class SignalAction(StrEnum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class Signal(BaseModel):
    symbol: str
    action: SignalAction
    confidence: float = Field(ge=0.0, le=1.0)
    price: Decimal = Field(gt=Decimal("0"))

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper().strip()


class OrderIntent(BaseModel):
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal = Field(gt=Decimal("0"))
    price: Decimal = Field(gt=Decimal("0"))
    stop_loss: Decimal | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper().strip()


class PortfolioState(BaseModel):
    equity: Decimal = Field(gt=Decimal("0"))
    daily_pnl: Decimal = Decimal("0")
    open_positions: int = Field(ge=0)


class RiskDecision(BaseModel):
    approved: bool
    reasons: list[str] = Field(default_factory=list)


class SymbolFilters(BaseModel):
    symbol: str
    price_min: Decimal = Field(gt=Decimal("0"))
    price_max: Decimal = Field(gt=Decimal("0"))
    price_tick_size: Decimal = Field(gt=Decimal("0"))
    qty_min: Decimal = Field(gt=Decimal("0"))
    qty_max: Decimal = Field(gt=Decimal("0"))
    qty_step_size: Decimal = Field(gt=Decimal("0"))
    min_notional: Decimal = Field(gt=Decimal("0"))

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper().strip()

"""Domain models for Sprint 0."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


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
    take_profit: Decimal | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper().strip()

    @model_validator(mode="after")
    def validate_take_profit_direction(self) -> "OrderIntent":
        if self.take_profit is None:
            return self
        if self.stop_loss is not None:
            if self.side == OrderSide.BUY:
                if not (self.stop_loss < self.price < self.take_profit):
                    raise ValueError(
                        f"BUY order requires stop_loss < price < take_profit, "
                        f"got {self.stop_loss} < {self.price} < {self.take_profit}"
                    )
            else:
                if not (self.take_profit < self.price < self.stop_loss):
                    raise ValueError(
                        f"SELL order requires take_profit < price < stop_loss, "
                        f"got {self.take_profit} < {self.price} < {self.stop_loss}"
                    )
        else:
            if self.side == OrderSide.BUY and self.take_profit <= self.price:
                raise ValueError(
                    f"BUY take_profit must be above price, "
                    f"got take_profit={self.take_profit} <= price={self.price}"
                )
            if self.side == OrderSide.SELL and self.take_profit >= self.price:
                raise ValueError(
                    f"SELL take_profit must be below price, "
                    f"got take_profit={self.take_profit} >= price={self.price}"
                )
        return self


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

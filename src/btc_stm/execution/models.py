"""Execution models for local paper trading only."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from btc_stm.domain import OrderSide


class ExecutionStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"


class Fill(BaseModel):
    symbol: str
    side: OrderSide
    price: Decimal = Field(gt=Decimal("0"))
    quantity: Decimal = Field(gt=Decimal("0"))
    fee: Decimal = Field(ge=Decimal("0"))
    fee_asset: str
    executed_at: datetime

    @field_validator("symbol", "fee_asset")
    @classmethod
    def normalize_upper(cls, value: str) -> str:
        return value.upper().strip()


class ExecutionReport(BaseModel):
    client_order_id: str
    symbol: str
    side: OrderSide
    status: ExecutionStatus
    requested_price: Decimal = Field(gt=Decimal("0"))
    requested_quantity: Decimal = Field(gt=Decimal("0"))
    filled_quantity: Decimal = Field(ge=Decimal("0"))
    average_fill_price: Decimal = Field(ge=Decimal("0"))
    notional: Decimal = Field(ge=Decimal("0"))
    total_fee: Decimal = Field(ge=Decimal("0"))
    reason: str | None = None
    created_at: datetime
    fills: list[Fill] = Field(default_factory=list)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper().strip()


class PaperPosition(BaseModel):
    symbol: str
    quantity: Decimal = Field(ge=Decimal("0"))
    average_entry_price: Decimal = Field(ge=Decimal("0"))

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper().strip()


class PaperPortfolio(BaseModel):
    cash_balance: Decimal = Field(ge=Decimal("0"))
    positions: dict[str, PaperPosition] = Field(default_factory=dict)
    realized_pnl: Decimal = Decimal("0")
    total_fees_paid: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))

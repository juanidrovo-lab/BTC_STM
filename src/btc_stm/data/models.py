"""Pydantic market data models for public data ingestion."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from btc_stm.data.normalizer import normalize_symbol

LOCAL_RECEIVE_TIME_TOLERANCE = timedelta(seconds=1)


class SymbolModel(BaseModel):
    symbol: str

    @field_validator("symbol")
    @classmethod
    def normalize_symbol_value(cls, value: str) -> str:
        return normalize_symbol(value)


class TimedMarketDataModel(SymbolModel):
    event_time: datetime
    local_receive_time: datetime

    @model_validator(mode="after")
    def validate_receive_time(self) -> Self:
        if self.local_receive_time + LOCAL_RECEIVE_TIME_TOLERANCE < self.event_time:
            raise ValueError(
                "local_receive_time must not be earlier than event_time beyond "
                "1 second clock skew tolerance"
            )
        return self


class TradeEvent(TimedMarketDataModel):
    trade_id: str | int
    price: Decimal = Field(gt=Decimal("0"))
    quantity: Decimal = Field(gt=Decimal("0"))
    is_buyer_maker: bool | None = None


class OrderBookLevel(BaseModel):
    price: Decimal = Field(gt=Decimal("0"))
    quantity: Decimal = Field(ge=Decimal("0"))


class OrderBookSnapshot(TimedMarketDataModel):
    last_update_id: int
    bids: list[OrderBookLevel] = Field(min_length=1)
    asks: list[OrderBookLevel] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_spread(self) -> Self:
        best_bid = max(level.price for level in self.bids)
        best_ask = min(level.price for level in self.asks)
        if best_bid >= best_ask:
            raise ValueError("best_bid must be lower than best_ask")
        return self


class OrderBookDelta(TimedMarketDataModel):
    first_update_id: int
    final_update_id: int
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]

    @model_validator(mode="after")
    def validate_update_range(self) -> Self:
        if self.final_update_id < self.first_update_id:
            raise ValueError("final_update_id must be greater than or equal to first_update_id")
        return self


class OHLCVBar(TimedMarketDataModel):
    interval: str
    open_time: datetime
    close_time: datetime
    open: Decimal = Field(gt=Decimal("0"))
    high: Decimal = Field(gt=Decimal("0"))
    low: Decimal = Field(gt=Decimal("0"))
    close: Decimal = Field(gt=Decimal("0"))
    volume: Decimal = Field(ge=Decimal("0"))

    @model_validator(mode="after")
    def validate_ohlcv_range(self) -> Self:
        if self.close_time <= self.open_time:
            raise ValueError("close_time must be greater than open_time")
        if self.high < self.open or self.high < self.close or self.high < self.low:
            raise ValueError("high must be greater than or equal to open, close, and low")
        if self.low > self.open or self.low > self.close:
            raise ValueError("low must be less than or equal to open and close")
        return self


class MarketDataEvent(BaseModel):
    event_type: str
    payload: TradeEvent | OrderBookSnapshot | OrderBookDelta | OHLCVBar

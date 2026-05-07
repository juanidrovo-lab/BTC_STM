from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from btc_stm.analytics.models import DrawdownPoint, ReturnPoint, TradeAnalytics


def test_return_point_rejects_non_finite_period_return() -> None:
    with pytest.raises(ValidationError, match="finite"):
        ReturnPoint(
            timestamp=datetime(2026, 5, 7, tzinfo=UTC),
            equity=Decimal("100"),
            period_return_pct=Decimal("NaN"),
        )


def test_drawdown_point_rejects_negative_drawdown() -> None:
    with pytest.raises(ValidationError):
        DrawdownPoint(
            timestamp=datetime(2026, 5, 7, tzinfo=UTC),
            equity=Decimal("100"),
            peak_equity=Decimal("120"),
            drawdown_pct=Decimal("-1"),
        )


def test_trade_analytics_rejects_non_finite_average_fill_price() -> None:
    with pytest.raises(ValidationError, match="finite"):
        TradeAnalytics(
            total_reports=1,
            filled_reports=1,
            rejected_reports=0,
            partially_filled_reports=0,
            total_notional=Decimal("100"),
            total_fees=Decimal("1"),
            average_fill_price=Decimal("Infinity"),
        )

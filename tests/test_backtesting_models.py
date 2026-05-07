from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from btc_stm.backtesting.models import BacktestConfig, EquityPoint


def test_backtest_config_rejects_non_positive_initial_cash() -> None:
    with pytest.raises(ValidationError):
        BacktestConfig(
            symbol="BTCUSDT",
            initial_cash=Decimal("0"),
            fee_rate_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
        )


def test_backtest_config_normalizes_symbol() -> None:
    config = BacktestConfig(
        symbol="BTC/USDT",
        initial_cash=Decimal("1000"),
        fee_rate_bps=Decimal("1"),
        slippage_bps=Decimal("2"),
    )

    assert config.symbol == "BTCUSDT"


def test_backtest_config_rejects_invalid_execute_on() -> None:
    with pytest.raises(ValidationError, match="execute_on"):
        BacktestConfig(
            symbol="BTCUSDT",
            initial_cash=Decimal("1000"),
            fee_rate_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
            execute_on="high",
        )


def test_equity_point_rejects_negative_equity_values() -> None:
    with pytest.raises(ValidationError):
        EquityPoint(
            timestamp=datetime(2026, 5, 7, tzinfo=UTC),
            equity=Decimal("-1"),
            cash_balance=Decimal("0"),
            position_value=Decimal("0"),
            realized_pnl=Decimal("0"),
        )

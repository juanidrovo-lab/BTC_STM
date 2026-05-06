"""BTC_STM package."""

from btc_stm.config import ENABLE_LIVE_TRADING, TRADING_MODE
from btc_stm.models import (
    OrderIntent,
    OrderSide,
    OrderType,
    PortfolioState,
    RiskDecision,
    Signal,
    SignalAction,
    SymbolFilters,
)
from btc_stm.risk import RiskManager

__all__ = [
    "__version__",
    "TRADING_MODE",
    "ENABLE_LIVE_TRADING",
    "SignalAction",
    "OrderSide",
    "OrderType",
    "Signal",
    "OrderIntent",
    "PortfolioState",
    "RiskDecision",
    "SymbolFilters",
    "RiskManager",
]
__version__ = "0.1.0"

"""Paper execution engine package."""

from btc_stm.execution.engine import PaperExecutionEngine
from btc_stm.execution.fees import calculate_fee
from btc_stm.execution.models import (
    ExecutionReport,
    ExecutionStatus,
    Fill,
    PaperPortfolio,
    PaperPosition,
)
from btc_stm.execution.paper_broker import PaperBroker
from btc_stm.execution.slippage import apply_slippage

__all__ = [
    "ExecutionReport",
    "ExecutionStatus",
    "Fill",
    "PaperBroker",
    "PaperExecutionEngine",
    "PaperPortfolio",
    "PaperPosition",
    "apply_slippage",
    "calculate_fee",
]

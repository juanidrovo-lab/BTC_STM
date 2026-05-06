"""Paper execution engine guarded by centralized risk controls."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from btc_stm.domain import OrderIntent, PortfolioState, SymbolFilters
from btc_stm.execution.models import ExecutionReport, ExecutionStatus, PaperPortfolio
from btc_stm.execution.paper_broker import PaperBroker
from btc_stm.execution.slippage import apply_slippage
from btc_stm.risk import RiskManager
from btc_stm.settings import Settings, TradingMode


class PaperExecutionEngine:
    def __init__(
        self,
        *,
        settings: Settings,
        risk_manager: RiskManager,
        broker: PaperBroker | None = None,
        slippage_bps: Decimal = Decimal("0"),
    ) -> None:
        if not slippage_bps.is_finite():
            raise ValueError("slippage_bps must be a finite decimal")
        if slippage_bps < 0:
            raise ValueError("slippage_bps must be greater than or equal to zero")
        self.settings = settings
        self.risk_manager = risk_manager
        self.broker = broker or PaperBroker()
        self.slippage_bps = slippage_bps

    def execute_order(
        self,
        *,
        order: OrderIntent,
        paper_portfolio: PaperPortfolio,
        risk_portfolio: PortfolioState,
        filters: SymbolFilters,
        market_price: Decimal,
    ) -> tuple[PaperPortfolio, ExecutionReport]:
        if self.settings.trading_mode is not TradingMode.PAPER:
            return paper_portfolio, self._rejected_report(
                order=order,
                reason="Order rejected: paper execution engine only supports paper mode.",
            )
        if not market_price.is_finite():
            return paper_portfolio, self._rejected_report(
                order=order,
                reason="Order rejected: market price must be a finite decimal.",
            )
        if market_price <= 0:
            return paper_portfolio, self._rejected_report(
                order=order,
                reason="Order rejected: market price must be greater than zero.",
            )

        risk_decision = self.risk_manager.evaluate(
            order=order,
            portfolio=risk_portfolio,
            filters=filters,
        )
        if not risk_decision.approved:
            return paper_portfolio, self._rejected_report(
                order=order,
                reason="; ".join(risk_decision.reasons),
            )

        fill_price = apply_slippage(market_price, order.side, self.slippage_bps)
        return self.broker.execute_order(order, paper_portfolio, fill_price)

    @staticmethod
    def _rejected_report(*, order: OrderIntent, reason: str) -> ExecutionReport:
        return ExecutionReport(
            client_order_id=str(uuid4()),
            symbol=order.symbol,
            side=order.side,
            status=ExecutionStatus.REJECTED,
            requested_price=order.price,
            requested_quantity=order.quantity,
            filled_quantity=Decimal("0"),
            average_fill_price=Decimal("0"),
            notional=Decimal("0"),
            total_fee=Decimal("0"),
            reason=reason,
            created_at=datetime.now(UTC),
            fills=[],
        )

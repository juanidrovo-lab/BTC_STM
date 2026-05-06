"""Local-only paper broker simulation."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from btc_stm.domain import OrderIntent, OrderSide
from btc_stm.execution.fees import calculate_fee
from btc_stm.execution.models import (
    ExecutionReport,
    ExecutionStatus,
    Fill,
    PaperPortfolio,
    PaperPosition,
)


class PaperBroker:
    """Simulates fills and portfolio updates without external connectivity."""

    def __init__(self, *, fee_rate_bps: Decimal = Decimal("10"), fee_asset: str = "USDT") -> None:
        if not fee_rate_bps.is_finite():
            raise ValueError("fee_rate_bps must be a finite decimal")
        if fee_rate_bps < 0:
            raise ValueError("fee_rate_bps must be greater than or equal to zero")
        self.fee_rate_bps = fee_rate_bps
        self.fee_asset = fee_asset.upper().strip()

    def execute_order(
        self,
        order: OrderIntent,
        portfolio: PaperPortfolio,
        fill_price: Decimal,
    ) -> tuple[PaperPortfolio, ExecutionReport]:
        invalid_reason = self._invalid_numeric_reason(order, fill_price)
        if invalid_reason is not None:
            return portfolio, self._rejected_report(order=order, reason=invalid_reason)

        notional = fill_price * order.quantity
        fee = calculate_fee(notional, self.fee_rate_bps)

        if order.side is OrderSide.BUY:
            return self._execute_paper_long(order, portfolio, fill_price, notional, fee)
        return self._execute_paper_exit(order, portfolio, fill_price, notional, fee)

    @staticmethod
    def _invalid_numeric_reason(order: OrderIntent, fill_price: Decimal) -> str | None:
        if not fill_price.is_finite():
            return "Order rejected: fill price must be a finite decimal."
        if fill_price <= 0:
            return "Order rejected: fill price must be greater than zero."
        values = [order.price, order.quantity, order.stop_loss]
        if not all(value is None or value.is_finite() for value in values):
            return "Order rejected: non-finite order numeric value detected."
        return None

    def _execute_paper_long(
        self,
        order: OrderIntent,
        portfolio: PaperPortfolio,
        fill_price: Decimal,
        notional: Decimal,
        fee: Decimal,
    ) -> tuple[PaperPortfolio, ExecutionReport]:
        total_cost = notional + fee
        if portfolio.cash_balance < total_cost:
            return portfolio, self._rejected_report(
                order=order,
                reason="Order rejected: insufficient paper cash balance.",
            )

        updated = portfolio.model_copy(deep=True)
        existing = updated.positions.get(order.symbol)
        if existing is None:
            updated.positions[order.symbol] = PaperPosition(
                symbol=order.symbol,
                quantity=order.quantity,
                average_entry_price=fill_price,
            )
        else:
            total_quantity = existing.quantity + order.quantity
            existing.average_entry_price = (
                (existing.quantity * existing.average_entry_price) + notional
            ) / total_quantity
            existing.quantity = total_quantity

        updated.cash_balance -= total_cost
        updated.total_fees_paid += fee
        return updated, self._filled_report(order=order, fill_price=fill_price, fee=fee)

    def _execute_paper_exit(
        self,
        order: OrderIntent,
        portfolio: PaperPortfolio,
        fill_price: Decimal,
        notional: Decimal,
        fee: Decimal,
    ) -> tuple[PaperPortfolio, ExecutionReport]:
        existing = portfolio.positions.get(order.symbol)
        if existing is None or existing.quantity < order.quantity:
            return portfolio, self._rejected_report(
                order=order,
                reason="Order rejected: insufficient paper position quantity.",
            )

        updated = portfolio.model_copy(deep=True)
        updated_position = updated.positions[order.symbol]
        updated_position.quantity -= order.quantity
        realized_pnl = (fill_price - updated_position.average_entry_price) * order.quantity - fee
        if updated_position.quantity == 0:
            del updated.positions[order.symbol]

        updated.cash_balance += notional - fee
        updated.realized_pnl += realized_pnl
        updated.total_fees_paid += fee
        return updated, self._filled_report(order=order, fill_price=fill_price, fee=fee)

    def _filled_report(
        self,
        *,
        order: OrderIntent,
        fill_price: Decimal,
        fee: Decimal,
    ) -> ExecutionReport:
        created_at = datetime.now(UTC)
        fill = Fill(
            symbol=order.symbol,
            side=order.side,
            price=fill_price,
            quantity=order.quantity,
            fee=fee,
            fee_asset=self.fee_asset,
            executed_at=created_at,
        )
        notional = fill_price * order.quantity
        return ExecutionReport(
            client_order_id=str(uuid4()),
            symbol=order.symbol,
            side=order.side,
            status=ExecutionStatus.FILLED,
            requested_price=order.price,
            requested_quantity=order.quantity,
            filled_quantity=order.quantity,
            average_fill_price=fill_price,
            notional=notional,
            total_fee=fee,
            reason=None,
            created_at=created_at,
            fills=[fill],
        )

    def _rejected_report(self, *, order: OrderIntent, reason: str) -> ExecutionReport:
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

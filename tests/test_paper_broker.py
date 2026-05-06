from decimal import Decimal

from btc_stm.domain import OrderIntent, OrderSide, OrderType
from btc_stm.execution.models import ExecutionStatus, PaperPortfolio, PaperPosition
from btc_stm.execution.paper_broker import PaperBroker


def make_order(side: OrderSide, quantity: Decimal = Decimal("1")) -> OrderIntent:
    return OrderIntent(
        symbol="BTCUSDT",
        side=side,
        order_type=OrderType.LIMIT,
        quantity=quantity,
        price=Decimal("100"),
        stop_loss=Decimal("90"),
    )


def test_paper_broker_has_no_real_order_methods() -> None:
    broker = PaperBroker()

    for method_name in ("buy", "sell", "create_order", "cancel_order", "place_order"):
        assert not hasattr(broker, method_name)


def test_paper_broker_buy_reduces_cash_and_creates_position() -> None:
    broker = PaperBroker(fee_rate_bps=Decimal("10"))
    portfolio = PaperPortfolio(cash_balance=Decimal("1000"))

    updated, report = broker.execute_order(make_order(OrderSide.BUY), portfolio, Decimal("100"))

    assert report.status is ExecutionStatus.FILLED
    assert updated.cash_balance == Decimal("899.9")
    assert updated.positions["BTCUSDT"].quantity == Decimal("1")
    assert updated.positions["BTCUSDT"].average_entry_price == Decimal("100")
    assert updated.total_fees_paid == Decimal("0.1")


def test_paper_broker_buy_increases_position_average_entry_price() -> None:
    broker = PaperBroker(fee_rate_bps=Decimal("0"))
    portfolio = PaperPortfolio(
        cash_balance=Decimal("1000"),
        positions={
            "BTCUSDT": PaperPosition(
                symbol="BTCUSDT",
                quantity=Decimal("1"),
                average_entry_price=Decimal("100"),
            )
        },
    )

    updated, report = broker.execute_order(make_order(OrderSide.BUY), portfolio, Decimal("200"))

    assert report.status is ExecutionStatus.FILLED
    assert updated.positions["BTCUSDT"].quantity == Decimal("2")
    assert updated.positions["BTCUSDT"].average_entry_price == Decimal("150")


def test_paper_broker_sell_increases_cash_and_reduces_position() -> None:
    broker = PaperBroker(fee_rate_bps=Decimal("10"))
    portfolio = PaperPortfolio(
        cash_balance=Decimal("1000"),
        positions={
            "BTCUSDT": PaperPosition(
                symbol="BTCUSDT",
                quantity=Decimal("2"),
                average_entry_price=Decimal("80"),
            )
        },
    )

    updated, report = broker.execute_order(make_order(OrderSide.SELL), portfolio, Decimal("100"))

    assert report.status is ExecutionStatus.FILLED
    assert updated.cash_balance == Decimal("1099.9")
    assert updated.positions["BTCUSDT"].quantity == Decimal("1")
    assert updated.realized_pnl == Decimal("19.9")
    assert updated.total_fees_paid == Decimal("0.1")


def test_paper_broker_sell_removes_zero_position() -> None:
    broker = PaperBroker(fee_rate_bps=Decimal("0"))
    portfolio = PaperPortfolio(
        cash_balance=Decimal("1000"),
        positions={
            "BTCUSDT": PaperPosition(
                symbol="BTCUSDT",
                quantity=Decimal("1"),
                average_entry_price=Decimal("80"),
            )
        },
    )

    updated, report = broker.execute_order(make_order(OrderSide.SELL), portfolio, Decimal("100"))

    assert report.status is ExecutionStatus.FILLED
    assert "BTCUSDT" not in updated.positions


def test_paper_broker_rejects_sell_greater_than_position() -> None:
    broker = PaperBroker()
    portfolio = PaperPortfolio(cash_balance=Decimal("1000"))

    updated, report = broker.execute_order(make_order(OrderSide.SELL), portfolio, Decimal("100"))

    assert updated == portfolio
    assert report.status is ExecutionStatus.REJECTED
    assert report.reason is not None
    assert "insufficient paper position" in report.reason


def test_paper_broker_rejects_buy_without_sufficient_cash() -> None:
    broker = PaperBroker(fee_rate_bps=Decimal("10"))
    portfolio = PaperPortfolio(cash_balance=Decimal("100"))

    updated, report = broker.execute_order(make_order(OrderSide.BUY), portfolio, Decimal("100"))

    assert updated == portfolio
    assert report.status is ExecutionStatus.REJECTED
    assert report.reason is not None
    assert "insufficient paper cash" in report.reason

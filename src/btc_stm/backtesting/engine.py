"""Deterministic local backtesting engine."""

from __future__ import annotations

from decimal import Decimal

from btc_stm.backtesting.data_feed import HistoricalDataFeed
from btc_stm.backtesting.metrics import build_backtest_metrics
from btc_stm.backtesting.models import (
    BacktestConfig,
    BacktestResult,
    BacktestTrade,
    EquityPoint,
    ScheduledOrder,
)
from btc_stm.data.models import OHLCVBar
from btc_stm.domain import PortfolioState, SymbolFilters
from btc_stm.execution.engine import PaperExecutionEngine
from btc_stm.execution.models import PaperPortfolio
from btc_stm.execution.paper_broker import PaperBroker
from btc_stm.risk import RiskManager
from btc_stm.settings import Settings, TradingMode


class BacktestEngine:
    def __init__(
        self,
        *,
        settings: Settings,
        risk_manager: RiskManager,
        filters: SymbolFilters,
    ) -> None:
        self.settings = settings
        self.risk_manager = risk_manager
        self.filters = filters

    def run(
        self,
        *,
        config: BacktestConfig,
        data_feed: HistoricalDataFeed,
        scheduled_orders: list[ScheduledOrder],
    ) -> BacktestResult:
        if self.settings.trading_mode is not TradingMode.PAPER:
            raise ValueError("BacktestEngine only supports paper mode.")

        portfolio = PaperPortfolio(cash_balance=config.initial_cash)
        trades: list[BacktestTrade] = []
        equity_curve: list[EquityPoint] = []
        pending_orders = sorted(scheduled_orders, key=lambda scheduled: scheduled.execute_at)
        next_order_index = 0
        execution_engine = PaperExecutionEngine(
            settings=self.settings,
            risk_manager=self.risk_manager,
            broker=PaperBroker(fee_rate_bps=config.fee_rate_bps),
            slippage_bps=config.slippage_bps,
        )

        for bar in data_feed:
            market_price = bar.open if config.execute_on == "open" else bar.close
            current_equity = self._calculate_equity(portfolio, config.symbol, bar.close)

            while (
                next_order_index < len(pending_orders)
                and pending_orders[next_order_index].execute_at <= bar.open_time
            ):
                scheduled_order = pending_orders[next_order_index]
                risk_portfolio = self._build_risk_portfolio(portfolio, current_equity)
                portfolio, report = execution_engine.execute_order(
                    order=scheduled_order.order,
                    paper_portfolio=portfolio,
                    risk_portfolio=risk_portfolio,
                    filters=self.filters,
                    market_price=market_price,
                )
                trades.append(
                    BacktestTrade(timestamp=bar.open_time, execution_report=report)
                )
                current_equity = self._calculate_equity(portfolio, config.symbol, bar.close)
                next_order_index += 1

            equity_curve.append(self._build_equity_point(portfolio, config.symbol, bar))

        ending_equity = equity_curve[-1].equity
        metrics = build_backtest_metrics(
            starting_equity=config.initial_cash,
            ending_equity=ending_equity,
            equity_curve=equity_curve,
            trades=trades,
            total_fees_paid=portfolio.total_fees_paid,
        )
        return BacktestResult(
            config=config,
            trades=trades,
            equity_curve=equity_curve,
            metrics=metrics,
        )

    @staticmethod
    def _build_risk_portfolio(
        portfolio: PaperPortfolio,
        current_equity: Decimal,
    ) -> PortfolioState:
        open_positions = sum(
            1 for position in portfolio.positions.values() if position.quantity > 0
        )
        return PortfolioState(
            equity=current_equity,
            daily_pnl=Decimal("0"),
            open_positions=open_positions,
        )

    @staticmethod
    def _build_equity_point(
        portfolio: PaperPortfolio,
        symbol: str,
        bar: OHLCVBar,
    ) -> EquityPoint:
        position_value = BacktestEngine._position_value(portfolio, symbol, bar.close)
        equity = portfolio.cash_balance + position_value
        return EquityPoint(
            timestamp=bar.open_time,
            equity=equity,
            cash_balance=portfolio.cash_balance,
            position_value=position_value,
            realized_pnl=portfolio.realized_pnl,
        )

    @staticmethod
    def _calculate_equity(
        portfolio: PaperPortfolio,
        symbol: str,
        mark_price: Decimal,
    ) -> Decimal:
        return portfolio.cash_balance + BacktestEngine._position_value(
            portfolio,
            symbol,
            mark_price,
        )

    @staticmethod
    def _position_value(
        portfolio: PaperPortfolio,
        symbol: str,
        mark_price: Decimal,
    ) -> Decimal:
        position = portfolio.positions.get(symbol)
        if position is None:
            return Decimal("0")
        return position.quantity * mark_price

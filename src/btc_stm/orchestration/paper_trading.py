"""Deterministic local paper trading orchestrator."""

from __future__ import annotations

import logging
from decimal import Decimal

logger = logging.getLogger("btc_stm.orchestration")

from btc_stm.analytics.report import build_performance_report
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
from btc_stm.execution.models import ExecutionReport, ExecutionStatus, PaperPortfolio
from btc_stm.execution.paper_broker import PaperBroker
from btc_stm.orchestration.events import make_event
from btc_stm.orchestration.models import (
    OrchestratorEvent,
    OrchestratorEventType,
    PaperTradingConfig,
    PaperTradingSessionResult,
)
from btc_stm.risk import RiskManager
from btc_stm.settings import Settings, TradingMode
from btc_stm.strategy.base import Strategy
from btc_stm.strategy.models import StrategyContext, StrategyDecision


class PaperTradingOrchestrator:
    def __init__(
        self,
        *,
        settings: Settings,
        risk_manager: RiskManager,
        filters: SymbolFilters,
        strategy: Strategy,
    ) -> None:
        self.settings = settings
        self.risk_manager = risk_manager
        self.filters = filters
        self.strategy = strategy

    def run(
        self,
        config: PaperTradingConfig,
        bars: list[OHLCVBar] | HistoricalDataFeed,
    ) -> PaperTradingSessionResult:
        data_feed = bars if isinstance(bars, HistoricalDataFeed) else HistoricalDataFeed(bars)
        events: list[OrchestratorEvent] = []
        try:
            self._validate_session(config=config, data_feed=data_feed)
            if self.settings.trading_mode is not TradingMode.PAPER:
                raise ValueError("PaperTradingOrchestrator only supports paper mode.")
            return self._run_validated_session(
                config=config,
                data_feed=data_feed,
                events=events,
            )
        except ValueError as exc:
            logger.error("SESSION_FAILED | config_error | %s", exc)
            self._append_failure_event(events, data_feed, str(exc))
            raise
        except Exception as exc:
            logger.error("SESSION_FAILED | unexpected_error | %s", exc, exc_info=True)
            self._append_failure_event(events, data_feed, str(exc))
            raise

    def _run_validated_session(
        self,
        *,
        config: PaperTradingConfig,
        data_feed: HistoricalDataFeed,
        events: list[OrchestratorEvent],
    ) -> PaperTradingSessionResult:
        portfolio = PaperPortfolio(cash_balance=config.initial_cash)
        execution_engine = PaperExecutionEngine(
            settings=self.settings,
            risk_manager=self.risk_manager,
            broker=PaperBroker(fee_rate_bps=config.fee_rate_bps),
            slippage_bps=config.slippage_bps,
        )
        history: list[OHLCVBar] = []
        decisions: list[StrategyDecision] = []
        scheduled_orders: list[ScheduledOrder] = []
        execution_reports: list[ExecutionReport] = []
        equity_curve: list[EquityPoint] = []

        for bar in data_feed:
            market_price = bar.open if config.execute_on == "open" else bar.close
            events.append(
                make_event(
                    OrchestratorEventType.BAR_RECEIVED,
                    timestamp=bar.open_time,
                    message="Bar received.",
                    metadata={"symbol": bar.symbol},
                )
            )
            portfolio = self._execute_due_orders(
                config=config,
                bar=bar,
                market_price=market_price,
                portfolio=portfolio,
                scheduled_orders=scheduled_orders,
                execution_engine=execution_engine,
                execution_reports=execution_reports,
                events=events,
            )
            history.append(bar)
            context = StrategyContext(
                symbol=config.symbol,
                current_bar=bar,
                history=list(history),
                portfolio=portfolio.model_copy(deep=True),
            )
            decision = self.strategy.on_bar(context)
            self._validate_decision(config=config, decision=decision, context=context)
            decisions.append(decision)
            events.append(
                make_event(
                    OrchestratorEventType.STRATEGY_DECISION,
                    timestamp=decision.timestamp,
                    message="Strategy decision generated.",
                    metadata={"strategy": self.strategy.name},
                )
            )
            self._schedule_decision_orders(
                config=config,
                data_feed=data_feed,
                decision=decision,
                scheduled_orders=scheduled_orders,
                events=events,
            )
            equity_point = self._build_equity_point(portfolio, config.symbol, bar)
            equity_curve.append(equity_point)
            events.append(
                make_event(
                    OrchestratorEventType.EQUITY_UPDATED,
                    timestamp=bar.open_time,
                    message="Equity updated.",
                    metadata={"equity": str(equity_point.equity)},
                )
            )

        backtest_result = self._build_backtest_result(
            config=config,
            execution_reports=execution_reports,
            equity_curve=equity_curve,
            portfolio=portfolio,
        )
        performance_report = build_performance_report(backtest_result)
        events.append(
            make_event(
                OrchestratorEventType.SESSION_COMPLETED,
                timestamp=data_feed.last_timestamp,
                message="Paper trading session completed.",
            )
        )
        return PaperTradingSessionResult(
            config=config,
            decisions=decisions,
            execution_reports=execution_reports,
            equity_curve=equity_curve,
            performance_report=performance_report,
            events=events,
        )

    @staticmethod
    def _append_failure_event(
        events: list[OrchestratorEvent],
        data_feed: HistoricalDataFeed,
        message: str,
    ) -> None:
        try:
            failure_timestamp = data_feed.first_timestamp
        except Exception:
            from datetime import UTC, datetime
            failure_timestamp = datetime.now(UTC)
        events.append(
            make_event(
                OrchestratorEventType.SESSION_FAILED,
                timestamp=failure_timestamp,
                message=f"Paper trading session failed: {message}",
            )
        )

    def _validate_session(
        self,
        *,
        config: PaperTradingConfig,
        data_feed: HistoricalDataFeed,
    ) -> None:
        if self.filters.symbol != config.symbol:
            raise ValueError("Symbol mismatch between paper trading config and filters.")
        for bar in data_feed:
            if bar.symbol != config.symbol:
                raise ValueError("Symbol mismatch between paper trading config and bars.")

    def _validate_decision(
        self,
        *,
        config: PaperTradingConfig,
        decision: StrategyDecision,
        context: StrategyContext,
    ) -> None:
        if decision.timestamp < context.current_bar.open_time:
            raise ValueError("Strategy decision timestamp must not be before current bar.")
        for order in decision.orders:
            if order.symbol != config.symbol:
                raise ValueError("Strategy order symbol must match paper trading config.")
            if order.stop_loss is None:
                raise ValueError("Strategy order must include stop_loss.")

    @staticmethod
    def _schedule_decision_orders(
        *,
        config: PaperTradingConfig,
        data_feed: HistoricalDataFeed,
        decision: StrategyDecision,
        scheduled_orders: list[ScheduledOrder],
        events: list[OrchestratorEvent],
    ) -> None:
        if not data_feed.first_timestamp <= decision.timestamp <= data_feed.last_timestamp:
            return
        for order in decision.orders:
            scheduled_orders.append(ScheduledOrder(execute_at=decision.timestamp, order=order))
            events.append(
                make_event(
                    OrchestratorEventType.ORDER_SCHEDULED,
                    timestamp=decision.timestamp,
                    message="Order scheduled for paper execution.",
                    metadata={"symbol": config.symbol, "side": order.side.value},
                )
            )

    def _execute_due_orders(
        self,
        *,
        config: PaperTradingConfig,
        bar: OHLCVBar,
        market_price: Decimal,
        portfolio: PaperPortfolio,
        scheduled_orders: list[ScheduledOrder],
        execution_engine: PaperExecutionEngine,
        execution_reports: list[ExecutionReport],
        events: list[OrchestratorEvent],
    ) -> PaperPortfolio:
        current_portfolio = portfolio
        due_orders = [
            scheduled for scheduled in scheduled_orders if scheduled.execute_at <= bar.open_time
        ]
        scheduled_orders[:] = [
            scheduled for scheduled in scheduled_orders if scheduled.execute_at > bar.open_time
        ]
        for scheduled_order in due_orders:
            risk_equity = self._calculate_equity(current_portfolio, config.symbol, market_price)
            risk_portfolio = self._build_risk_portfolio(current_portfolio, risk_equity)
            current_portfolio, report = execution_engine.execute_order(
                order=scheduled_order.order,
                paper_portfolio=current_portfolio,
                risk_portfolio=risk_portfolio,
                filters=self.filters,
                market_price=market_price,
            )
            execution_reports.append(report)
            event_type = (
                OrchestratorEventType.ORDER_REJECTED
                if report.status is ExecutionStatus.REJECTED
                else OrchestratorEventType.ORDER_EXECUTED
            )
            events.append(
                make_event(
                    event_type,
                    timestamp=bar.open_time,
                    message="Order rejected." if event_type is OrchestratorEventType.ORDER_REJECTED else "Order executed.",
                    metadata={"status": report.status.value, "symbol": report.symbol},
                )
            )
        return current_portfolio

    @staticmethod
    def _build_risk_portfolio(
        portfolio: PaperPortfolio,
        current_equity: Decimal,
    ) -> PortfolioState:
        open_positions = sum(
            1 for position in portfolio.positions.values() if position.quantity > 0
        )
        # realized_pnl accumulates from PaperBroker on every closed trade.
        # Serializable from portfolio state → Neon-ready: swap portfolio read
        # for a DB query when migrating to cloud persistence.
        return PortfolioState(
            equity=current_equity,
            daily_pnl=portfolio.realized_pnl,
            open_positions=open_positions,
        )

    @staticmethod
    def _build_equity_point(
        portfolio: PaperPortfolio,
        symbol: str,
        bar: OHLCVBar,
    ) -> EquityPoint:
        position_value = PaperTradingOrchestrator._position_value(
            portfolio,
            symbol,
            bar.close,
        )
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
        return portfolio.cash_balance + PaperTradingOrchestrator._position_value(
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

    @staticmethod
    def _build_backtest_result(
        *,
        config: PaperTradingConfig,
        execution_reports: list[ExecutionReport],
        equity_curve: list[EquityPoint],
        portfolio: PaperPortfolio,
    ) -> BacktestResult:
        trades = [
            BacktestTrade(timestamp=report.created_at, execution_report=report)
            for report in execution_reports
        ]
        ending_equity = equity_curve[-1].equity
        metrics = build_backtest_metrics(
            starting_equity=config.initial_cash,
            ending_equity=ending_equity,
            equity_curve=equity_curve,
            trades=trades,
            total_fees_paid=portfolio.total_fees_paid,
        )
        return BacktestResult(
            config=BacktestConfig(
                symbol=config.symbol,
                initial_cash=config.initial_cash,
                fee_rate_bps=config.fee_rate_bps,
                slippage_bps=config.slippage_bps,
                execute_on=config.execute_on,
            ),
            trades=trades,
            equity_curve=equity_curve,
            metrics=metrics,
        )

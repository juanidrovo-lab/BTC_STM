"""Vercel serverless function — GET/POST /api/backtest.

GET  — returns API documentation / schema.
POST — runs a backtest from the provided bars and returns metrics.

POST body (JSON):
    {
        "symbol": "BTCUSDT",
        "initial_cash": "10000",
        "fee_rate_bps": "10",
        "slippage_bps": "5",
        "bars": [
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "open": "42000",
                "high": "43000",
                "low": "41000",
                "close": "42500",
                "volume": "100"
            },
            ...
        ]
    }

Response (POST):
    {"status": "ok", "metrics": {...}}
"""

from __future__ import annotations

import json
from decimal import Decimal
from http.server import BaseHTTPRequestHandler

_SCHEMA = {
    "endpoint": "/api/backtest",
    "methods": ["GET", "POST"],
    "GET": "Returns this schema.",
    "POST": {
        "body": {
            "symbol": "string — e.g. 'BTCUSDT'",
            "initial_cash": "string (decimal) — e.g. '10000'",
            "fee_rate_bps": "string (decimal, optional, default '10')",
            "slippage_bps": "string (decimal, optional, default '5')",
            "bars": [
                {
                    "timestamp": "ISO-8601 datetime string",
                    "open": "string (decimal)",
                    "high": "string (decimal)",
                    "low": "string (decimal)",
                    "close": "string (decimal)",
                    "volume": "string (decimal)",
                }
            ],
        },
        "response": {
            "status": "ok",
            "metrics": {
                "total_return_pct": "float",
                "sharpe_ratio": "float",
                "max_drawdown_pct": "float",
                "total_trades": "int",
                "winning_trades": "int",
                "losing_trades": "int",
                "win_rate_pct": "float",
                "final_equity": "string (decimal)",
            },
        },
    },
}


class handler(BaseHTTPRequestHandler):  # noqa: N801
    def do_GET(self) -> None:  # noqa: N802
        self._respond(200, _SCHEMA)

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            body: dict[str, object] = json.loads(raw_body)
        except json.JSONDecodeError:
            self._respond(400, {"status": "error", "error": "Invalid JSON body."})
            return

        symbol = body.get("symbol", "BTCUSDT")
        initial_cash_raw = body.get("initial_cash", "10000")
        fee_rate_bps_raw = body.get("fee_rate_bps", "10")
        slippage_bps_raw = body.get("slippage_bps", "5")
        bars_raw = body.get("bars", [])

        if not isinstance(bars_raw, list) or len(bars_raw) < 2:
            self._respond(
                400,
                {"status": "error", "error": "bars must be an array with at least 2 entries."},
            )
            return

        try:
            from datetime import datetime  # noqa: PLC0415

            from btc_stm.backtesting.data_feed import HistoricalDataFeed  # noqa: PLC0415
            from btc_stm.backtesting.engine import BacktestEngine  # noqa: PLC0415
            from btc_stm.backtesting.models import BacktestConfig  # noqa: PLC0415
            from btc_stm.data.models import OHLCVBar  # noqa: PLC0415
            from btc_stm.domain import SymbolFilters  # noqa: PLC0415
            from btc_stm.risk import RiskManager  # noqa: PLC0415
            from btc_stm.settings import Settings  # noqa: PLC0415

            ohlcv_bars: list[OHLCVBar] = []
            for bar_dict in bars_raw:
                if not isinstance(bar_dict, dict):
                    self._respond(400, {"status": "error", "error": "Each bar must be an object."})
                    return
                ts_raw = bar_dict.get("timestamp", "")
                ohlcv_bars.append(
                    OHLCVBar(
                        timestamp=datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00")),
                        open=Decimal(str(bar_dict.get("open", "0"))),
                        high=Decimal(str(bar_dict.get("high", "0"))),
                        low=Decimal(str(bar_dict.get("low", "0"))),
                        close=Decimal(str(bar_dict.get("close", "0"))),
                        volume=Decimal(str(bar_dict.get("volume", "0"))),
                    )
                )

            config = BacktestConfig(
                symbol=str(symbol),
                initial_cash=Decimal(str(initial_cash_raw)),
                fee_rate_bps=Decimal(str(fee_rate_bps_raw)),
                slippage_bps=Decimal(str(slippage_bps_raw)),
            )

            settings = Settings()
            risk_manager = RiskManager(settings=settings)
            filters = SymbolFilters(symbol=config.symbol)
            engine = BacktestEngine(
                settings=settings,
                risk_manager=risk_manager,
                filters=filters,
            )

            feed = HistoricalDataFeed(bars=ohlcv_bars, symbol=config.symbol)
            result = engine.run(config=config, data_feed=feed, scheduled_orders=[])

            metrics_dict = {
                "total_return_pct": float(result.metrics.total_return_pct),
                "sharpe_ratio": float(result.metrics.sharpe_ratio),
                "max_drawdown_pct": float(result.metrics.max_drawdown_pct),
                "total_trades": result.metrics.total_trades,
                "winning_trades": result.metrics.winning_trades,
                "losing_trades": result.metrics.losing_trades,
                "win_rate_pct": float(result.metrics.win_rate_pct),
                "final_equity": str(result.equity_curve[-1].equity) if result.equity_curve else str(config.initial_cash),
            }
            self._respond(200, {"status": "ok", "metrics": metrics_dict})

        except Exception as exc:  # noqa: BLE001
            self._respond(500, {"status": "error", "error": str(exc)})

    def _respond(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass

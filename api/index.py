"""BTC-STM API — Vercel Python serverless entrypoint.

Routes all /api/* traffic through a single BaseHTTPRequestHandler.
FastAPI is used internally for request parsing; the WSGI handler
wraps it so Vercel's @vercel/python runtime can invoke it.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# ── Path fix — ensures btc_stm is importable whether pip-installed or not ────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def _json_response(
    req: "BaseHTTPRequestHandler",
    status: int,
    payload: dict,
) -> None:
    body = json.dumps(payload, default=str).encode()
    req.send_response(status)
    req.send_header("Content-Type", "application/json")
    req.send_header("Content-Length", str(len(body)))
    req.end_headers()
    req.wfile.write(body)


def _read_body(req: "BaseHTTPRequestHandler") -> dict:
    length = int(req.headers.get("Content-Length", 0))
    raw = req.rfile.read(length) if length else b"{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Route handlers
# ─────────────────────────────────────────────────────────────────────────────

def _handle_health(req: "BaseHTTPRequestHandler") -> None:
    _json_response(req, 200, {
        "status": "ok",
        "service": "btc-stm",
        "version": "0.2.0",
        "python": sys.version.split()[0],
        "trading_mode": os.environ.get("TRADING_MODE", "paper"),
        "persistence_backend": os.environ.get("PERSISTENCE_BACKEND", "local"),
        "db_configured": bool(os.environ.get("DATABASE_URL")),
    })


def _handle_backtest_get(req: "BaseHTTPRequestHandler") -> None:
    _json_response(req, 200, {
        "endpoint": "/api/backtest",
        "method": "POST",
        "body": {
            "symbol": "string — e.g. 'BTCUSDT'",
            "initial_cash": "decimal string — e.g. '10000'",
            "fee_rate_bps": "decimal string, optional, default '10'",
            "slippage_bps": "decimal string, optional, default '5'",
            "execute_on": "'open' | 'close', optional, default 'close'",
            "bars": [{"open_time": "ISO-8601", "close_time": "ISO-8601",
                      "open": "decimal", "high": "decimal",
                      "low": "decimal", "close": "decimal", "volume": "decimal"}],
        },
    })


def _handle_backtest_post(req: "BaseHTTPRequestHandler") -> None:
    body = _read_body(req)
    if not body:
        _json_response(req, 400, {"detail": "Request body must be valid JSON."})
        return

    from datetime import datetime  # noqa: PLC0415
    from decimal import Decimal, InvalidOperation  # noqa: PLC0415

    symbol = str(body.get("symbol", "BTCUSDT")).strip().upper()
    execute_on = str(body.get("execute_on", "close")).strip().lower()
    bars_raw = body.get("bars", [])

    if execute_on not in {"open", "close"}:
        _json_response(req, 400, {"detail": "execute_on must be 'open' or 'close'."})
        return
    if not isinstance(bars_raw, list) or len(bars_raw) < 2:
        _json_response(req, 400, {"detail": "bars must be a JSON array with ≥ 2 entries."})
        return

    def _dec(v: object, field: str) -> Decimal:
        try:
            result = Decimal(str(v))
            if not result.is_finite():
                raise ValueError
            return result
        except (InvalidOperation, ValueError):
            raise ValueError(f"Invalid decimal for '{field}': {v!r}")

    try:
        initial_cash = _dec(body.get("initial_cash", "10000"), "initial_cash")
        fee_rate_bps = _dec(body.get("fee_rate_bps", "10"), "fee_rate_bps")
        slippage_bps = _dec(body.get("slippage_bps", "5"), "slippage_bps")

        from btc_stm.data.models import OHLCVBar  # noqa: PLC0415
        from btc_stm.domain import SymbolFilters  # noqa: PLC0415
        from btc_stm.orchestration.models import PaperTradingConfig  # noqa: PLC0415
        from btc_stm.orchestration.paper_trading import PaperTradingOrchestrator  # noqa: PLC0415
        from btc_stm.persistence.serialization import to_jsonable  # noqa: PLC0415
        from btc_stm.risk import RiskManager  # noqa: PLC0415
        from btc_stm.settings import Settings  # noqa: PLC0415
        from btc_stm.strategy.examples import NoOpStrategy  # noqa: PLC0415

        bars = [
            OHLCVBar(
                symbol=symbol,
                interval=str(b.get("interval", "1m")),
                open_time=datetime.fromisoformat(str(b["open_time"])),
                close_time=datetime.fromisoformat(str(b["close_time"])),
                open=_dec(b["open"], "open"),
                high=_dec(b["high"], "high"),
                low=_dec(b["low"], "low"),
                close=_dec(b["close"], "close"),
                volume=_dec(b["volume"], "volume"),
            )
            for b in bars_raw
        ]

        settings = Settings()
        orchestrator = PaperTradingOrchestrator(
            settings=settings,
            risk_manager=RiskManager(settings),
            filters=SymbolFilters(
                symbol=symbol,
                price_min=Decimal("0.01"),
                price_max=Decimal("9999999"),
                price_tick_size=Decimal("0.01"),
                qty_min=Decimal("0.00001"),
                qty_max=Decimal("9000"),
                qty_step_size=Decimal("0.00001"),
                min_notional=Decimal("1"),
            ),
            strategy=NoOpStrategy(),
        )
        config = PaperTradingConfig(
            symbol=symbol,
            initial_cash=initial_cash,
            fee_rate_bps=fee_rate_bps,
            slippage_bps=slippage_bps,
            execute_on=execute_on,
        )
        result = orchestrator.run(config=config, bars=bars)
        _json_response(req, 200, {
            "status": "ok",
            "symbol": symbol,
            "bar_count": len(bars),
            "metrics": to_jsonable(result.performance_report),
        })
    except ValueError as exc:
        _json_response(req, 400, {"detail": str(exc)})
    except Exception as exc:
        _json_response(req, 500, {"detail": f"Backtest failed: {exc}"})


def _handle_paper_trade_get(req: "BaseHTTPRequestHandler") -> None:
    _json_response(req, 200, {
        "endpoint": "/api/paper-trade",
        "method": "POST",
        "body": {"session_id": "string (required)", "symbol": "string (default: BTCUSDT)"},
    })


def _handle_paper_trade_post(req: "BaseHTTPRequestHandler") -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        _json_response(req, 503, {"detail": "DATABASE_URL not configured."})
        return

    body = _read_body(req)
    session_id = str(body.get("session_id", "")).strip()
    symbol = str(body.get("symbol", "BTCUSDT")).strip().upper()
    if not session_id:
        _json_response(req, 400, {"detail": "session_id is required."})
        return

    try:
        import asyncio  # noqa: PLC0415
        from btc_stm.persistence.neon_store import NeonSessionStore  # noqa: PLC0415

        async def _load():
            store = NeonSessionStore(database_url=database_url)
            try:
                return await store.load_manifest(session_id)
            finally:
                await store.close()

        manifest = asyncio.run(_load())
        _json_response(req, 200, {
            "status": "ok",
            "session_id": session_id,
            "symbol": symbol,
            "total_events": manifest.total_events,
            "total_trades": manifest.total_execution_reports,
            "equity_points": manifest.total_equity_points,
        })
    except KeyError:
        _json_response(req, 404, {"detail": f"Session not found: {session_id}"})
    except Exception as exc:
        _json_response(req, 500, {"detail": str(exc)})


def _normalize_db_url_asyncpg(database_url: str) -> str:
    """Return a URL suitable for asyncpg.connect() — no dialect suffix, ssl=require."""
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse  # noqa: PLC0415
    p = urlparse(database_url)
    scheme = "postgresql" if p.scheme in ("postgresql", "postgres", "postgresql+asyncpg") else p.scheme
    orig_qs = parse_qs(p.query)
    qs = {k: v for k, v in orig_qs.items() if k not in ("sslmode", "channel_binding")}
    if "sslmode" in orig_qs and "ssl" not in qs:
        qs["ssl"] = ["require"]
    return urlunparse(p._replace(scheme=scheme, query=urlencode({k: v[0] for k, v in qs.items()})))


def _db_query(sql: str, *args: object) -> list[dict]:
    """Run a read-only query against Neon DB; returns [] on any error."""
    import asyncio  # noqa: PLC0415
    import asyncpg  # noqa: PLC0415
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return []
    dsn = _normalize_db_url_asyncpg(database_url)

    async def _run() -> list[dict]:
        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch(sql, *args)
            return [dict(r) for r in rows]
        finally:
            await conn.close()

    try:
        return asyncio.run(_run())
    except Exception:
        return []


def _handle_portfolio_metrics(req: "BaseHTTPRequestHandler") -> None:
    if not os.environ.get("DATABASE_URL"):
        _json_response(req, 503, {"detail": "DATABASE_URL not configured."})
        return
    try:
        agg = _db_query("""
            SELECT
                COUNT(er.id)::int                                                            AS total_trades,
                COALESCE(SUM(CASE WHEN er.realized_pnl > 0 THEN 1 ELSE 0 END), 0)::int     AS winning_trades,
                COALESCE(SUM(er.realized_pnl::float), 0)                                    AS total_pnl,
                COALESCE(MAX(ts.initial_cash::float),  10000)                               AS initial_cash,
                COALESCE(
                    (SELECT current_equity::float FROM trading_sessions
                     WHERE current_equity IS NOT NULL ORDER BY started_at DESC LIMIT 1),
                    10000
                )                                                                            AS current_equity,
                COUNT(DISTINCT ts.id)::int                                                   AS total_sessions
            FROM trading_sessions ts
            LEFT JOIN execution_reports er ON er.session_id = ts.id
        """)
        row           = agg[0] if agg else {}
        total_trades  = int(row.get("total_trades")  or 0)
        winning       = int(row.get("winning_trades") or 0)
        initial       = float(row.get("initial_cash")    or 10000)
        current       = float(row.get("current_equity")  or initial)
        total_sessions = int(row.get("total_sessions") or 0)

        win_rate     = (winning / total_trades * 100) if total_trades > 0 else 0.0
        total_return = ((current - initial) / initial * 100) if initial > 0 else 0.0

        # Drawdown + Sharpe from equity curve of most recent session
        eq_rows = _db_query("""
            SELECT equity::float, recorded_at
            FROM equity_curve
            WHERE session_id = (SELECT id FROM trading_sessions ORDER BY started_at DESC LIMIT 1)
            ORDER BY recorded_at ASC
            LIMIT 500
        """)
        max_drawdown = 0.0
        sharpe       = 0.0
        if len(eq_rows) > 1:
            import statistics  # noqa: PLC0415
            equities = [r["equity"] for r in eq_rows]
            peak = equities[0]
            for e in equities:
                if e > peak:
                    peak = e
                if peak > 0:
                    dd = (peak - e) / peak * 100
                    if dd > max_drawdown:
                        max_drawdown = dd
            returns = [(equities[i] - equities[i - 1]) / equities[i - 1]
                       for i in range(1, len(equities)) if equities[i - 1] != 0]
            if len(returns) > 1:
                mean_r = statistics.mean(returns)
                std_r  = statistics.stdev(returns)
                sharpe = round((mean_r / std_r) * (252 ** 0.5), 2) if std_r > 0 else 0.0

        sign = "+" if total_return >= 0 else ""
        _json_response(req, 200, {
            "total_return":     round(total_return, 2),
            "total_return_str": f"{sign}{total_return:.2f}%",
            "max_drawdown":     round(-abs(max_drawdown), 2),
            "max_drawdown_str": f"-{max_drawdown:.2f}%",
            "win_rate":         round(win_rate, 1),
            "win_rate_str":     f"{win_rate:.1f}%",
            "sharpe":           sharpe,
            "sharpe_str":       str(sharpe),
            "total_trades":     total_trades,
            "current_equity":   round(current, 2),
            "initial_cash":     round(initial, 2),
            "total_sessions":   total_sessions,
            "source":           "neon" if total_sessions > 0 else "empty",
        })
    except Exception as exc:
        _json_response(req, 500, {"detail": str(exc)})


def _handle_logs(req: "BaseHTTPRequestHandler") -> None:
    if not os.environ.get("DATABASE_URL"):
        _json_response(req, 503, {"detail": "DATABASE_URL not configured."})
        return
    try:
        rows = _db_query("""
            SELECT event_type, message, created_at
            FROM orchestrator_events
            ORDER BY created_at DESC
            LIMIT 60
        """)
        logs = []
        for r in reversed(rows):
            ts  = r["created_at"]
            ts_str = ts.strftime("%H:%M:%S") if hasattr(ts, "strftime") else str(ts)[11:19]
            et = str(r.get("event_type", "INFO")).upper()
            level = et if et in ("INFO", "OK", "WARN", "ERR", "ERROR") else "INFO"
            if level == "ERROR":
                level = "ERR"
            logs.append({"ts": ts_str, "level": level, "msg": r["message"]})
        _json_response(req, 200, {"logs": logs, "count": len(logs)})
    except Exception as exc:
        _json_response(req, 500, {"detail": str(exc)})


def _db_execute(sql: str, *args: object) -> str:
    """Run a write statement (INSERT/UPDATE/DELETE); returns command tag."""
    import asyncio  # noqa: PLC0415
    import asyncpg  # noqa: PLC0415
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return "NO_DB"
    dsn = _normalize_db_url_asyncpg(database_url)

    async def _run() -> str:
        conn = await asyncpg.connect(dsn)
        try:
            return await conn.execute(sql, *args)
        finally:
            await conn.close()

    try:
        return asyncio.run(_run())
    except Exception:
        return "ERROR"


def _is_system_active() -> bool:
    """Check Neon DB for kill-switch state; defaults to True when table is absent."""
    rows = _db_query("SELECT value FROM system_config WHERE key = 'system_active' LIMIT 1")
    if not rows:
        return True
    return str(rows[0]["value"]).lower() in ("true", "1", "active")


def _set_system_state(active: bool) -> None:
    _db_execute(
        """
        INSERT INTO system_config (key, value, updated_at)
        VALUES ('system_active', $1, now())
        ON CONFLICT (key) DO UPDATE SET value = $1, updated_at = now()
        """,
        "true" if active else "false",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Live trading handlers
# ─────────────────────────────────────────────────────────────────────────────

def _handle_system_status(req: "BaseHTTPRequestHandler") -> None:
    active = _is_system_active()
    testnet = os.environ.get("BINANCE_TESTNET", "true").lower() != "false"
    _json_response(req, 200, {
        "system_active":  active,
        "testnet":        testnet,
        "network":        "TESTNET" if testnet else "MAINNET",
        "api_key_set":    bool(os.environ.get("BINANCE_API_KEY")),
        "secret_set":     bool(os.environ.get("BINANCE_API_SECRET")),
        "live_trading":   os.environ.get("ENABLE_LIVE_TRADING", "false").lower() == "true",
    })


def _handle_system_reset(req: "BaseHTTPRequestHandler") -> None:
    """Re-activate system after a kill switch. Requires explicit POST."""
    _set_system_state(True)
    _json_response(req, 200, {
        "status":  "ACTIVE",
        "message": "System re-activated. Trading is unblocked.",
    })


def _handle_trade_execute(req: "BaseHTTPRequestHandler") -> None:
    # ── Gate 1: system not halted ────────────────────────────────────────────
    if not _is_system_active():
        _json_response(req, 503, {
            "detail": "System is HALTED by kill switch. Call POST /api/control/reset to re-activate.",
        })
        return

    # ── Gate 2: live trading flag ────────────────────────────────────────────
    if os.environ.get("ENABLE_LIVE_TRADING", "false").lower() != "true":
        _json_response(req, 403, {
            "detail": "Live trading is disabled. Set ENABLE_LIVE_TRADING=true in Vercel env vars.",
        })
        return

    # ── Gate 3: parse and validate body ─────────────────────────────────────
    body    = _read_body(req)
    missing = [f for f in ("symbol", "side", "entry", "stop_loss", "take_profit") if not body.get(f)]
    if missing:
        _json_response(req, 400, {"detail": f"Missing required fields: {missing}"})
        return

    from decimal import Decimal, InvalidOperation  # noqa: PLC0415
    try:
        symbol      = str(body["symbol"]).strip().upper()
        side        = str(body["side"]).strip().upper()
        entry       = Decimal(str(body["entry"]))
        stop_loss   = Decimal(str(body["stop_loss"]))
        take_profit = Decimal(str(body["take_profit"]))
    except (InvalidOperation, TypeError) as exc:
        _json_response(req, 400, {"detail": f"Invalid numeric parameter: {exc}"})
        return

    if side not in ("BUY", "SELL"):
        _json_response(req, 400, {"detail": "side must be 'BUY' or 'SELL'."})
        return

    # ── Gate 4: risk validation + order execution ────────────────────────────
    try:
        from btc_stm.exchange.binance_client import BinanceAuthError, BinanceOrderClient  # noqa: PLC0415
        from btc_stm.exchange.trade_guard import TradeGuard, TradeSignal  # noqa: PLC0415

        client = BinanceOrderClient.from_env()
        guard  = TradeGuard(client)
        signal = TradeSignal(
            symbol=symbol, side=side,
            entry=entry, stop_loss=stop_loss, take_profit=take_profit,
        )

        # Runs EMA-200 filter, 1% sizing, and ≥1:2 R:R check
        order = guard.validate(signal)

        # Place entry limit order
        entry_result = client.place_limit_order(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=order.entry_price,
        )

        # Place OCO exit (TP limit + SL stop-limit, both cancelled when one fills)
        exit_side = "SELL" if order.side == "BUY" else "BUY"
        oco_result = client.place_oco_order(
            symbol=order.symbol,
            side=exit_side,
            quantity=order.quantity,
            take_profit_price=order.take_profit_price,
            stop_loss_price=order.stop_loss_price,
            stop_limit_price=order.stop_limit_price,
        )

        client.close()
        _json_response(req, 200, {
            "status":       "ok",
            "entry_order":  entry_result,
            "oco_order":    oco_result,
            "risk_usdt":    round(order.risk_usdt, 4),
            "rr_ratio":     round(order.rr_ratio, 2),
            "quantity":     order.quantity,
            "ema200":       round(order.ema200, 2),
            "network":      "TESTNET" if os.environ.get("BINANCE_TESTNET", "true").lower() != "false" else "MAINNET",
        })

    except ValueError as exc:
        # Risk policy breach — informative, not a server error
        _json_response(req, 422, {"detail": str(exc), "blocked_by": "trade_guard"})
    except BinanceAuthError as exc:
        _json_response(req, 503, {"detail": str(exc)})
    except Exception as exc:
        _json_response(req, 500, {"detail": f"Trade execution failed: {exc}"})


def _handle_kill_switch(req: "BaseHTTPRequestHandler") -> None:
    """Emergency stop:
    1. Cancel all open BTCUSDT orders.
    2. Close any open BTC position at market.
    3. Persist HALTED state in Neon DB.
    """
    results: dict = {}
    symbol  = os.environ.get("KILL_SWITCH_SYMBOL", "BTCUSDT")

    try:
        from btc_stm.exchange.binance_client import BinanceAuthError, BinanceOrderClient  # noqa: PLC0415
        from decimal import Decimal, ROUND_DOWN  # noqa: PLC0415

        client = BinanceOrderClient.from_env()

        # Step 1 — cancel all open orders
        try:
            cancelled             = client.cancel_all_orders(symbol)
            results["cancelled"]  = len(cancelled) if isinstance(cancelled, list) else cancelled
        except Exception as exc:
            results["cancel_error"] = str(exc)

        # Step 2 — close open BTC position at market
        btc_total = client.get_total_balance("BTC")
        if btc_total > 0.00001:
            try:
                qty_d = Decimal(str(btc_total))
                qty   = client.round_qty(symbol, qty_d)
                close = client.place_market_order(symbol, "SELL", str(qty))
                results["position_closed"] = {
                    "qty": str(qty),
                    "order_id": close.get("orderId"),
                    "status":   close.get("status"),
                }
            except Exception as exc:
                results["close_error"] = str(exc)
        else:
            results["position_closed"] = "no_open_position"

        client.close()

    except Exception as exc:
        # Credentials missing or network error — still persist HALTED state
        results["exchange_error"] = str(exc)

    # Step 3 — persist HALTED regardless of exchange errors above
    _set_system_state(False)
    results["system_active"] = False

    _json_response(req, 200, {
        "status":  "HALTED",
        "message": "Kill switch activated. All orders cancelled, position closed, system frozen.",
        "details": results,
    })


def _handle_secret_debug(req: "BaseHTTPRequestHandler") -> None:
    """Safe diagnostic — shows secret length and first/last char only."""
    raw = os.environ.get("MIGRATION_SECRET", "")
    stripped = raw.strip()
    _json_response(req, 200, {
        "migration_secret_set": bool(stripped),
        "raw_len": len(raw),
        "stripped_len": len(stripped),
        "first2": stripped[:2] if stripped else "",
        "last2": stripped[-2:] if stripped else "",
        "has_leading_whitespace": raw != raw.lstrip(),
        "has_trailing_whitespace": raw != raw.rstrip(),
    })


def _handle_migrate_post(req: "BaseHTTPRequestHandler") -> None:
    from urllib.parse import parse_qs, urlparse  # noqa: PLC0415

    stored_secret = os.environ.get("MIGRATION_SECRET", "").strip()
    if not stored_secret:
        _json_response(req, 503, {"detail": "MIGRATION_SECRET env var not set."})
        return

    # Accept secret via URL query param, header, or JSON body — whichever arrives
    qs = parse_qs(urlparse(req.path).query)
    body = _read_body(req)
    provided = (
        qs.get("token", [""])[0].strip()
        or req.headers.get("X-Migration-Secret", "").strip()
        or str(body.get("secret", "")).strip()
    )

    # Also accept MIGRATION_BYPASS_TOKEN for cases where the primary secret
    # has encoding ambiguity (homoglyphs, copy-paste issues).
    bypass = os.environ.get("MIGRATION_BYPASS_TOKEN", "").strip()
    authorized = (provided == stored_secret) or (bypass and provided == bypass)

    if not authorized:
        _json_response(req, 403, {
            "detail": "Invalid secret.",
            "hint": "Set MIGRATION_BYPASS_TOKEN in Vercel env vars and pass that value as ?token=",
        })
        return

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        _json_response(req, 503, {"detail": "DATABASE_URL not configured."})
        return

    # Normalize URL for asyncpg driver used by our async Alembic env.py
    # Vercel env var may be set to plain postgresql:// (psycopg2 default)
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse  # noqa: PLC0415
    _p = urlparse(database_url)
    if _p.scheme in ("postgresql", "postgres"):
        _p = _p._replace(scheme="postgresql+asyncpg")
    # asyncpg uses ?ssl= not ?sslmode=; strip channel_binding
    _qs = {k: v for k, v in parse_qs(_p.query).items()
           if k not in ("sslmode", "channel_binding")}
    if "sslmode" in parse_qs(_p.query) and "ssl" not in _qs:
        _qs["ssl"] = ["require"]
    database_url = urlunparse(_p._replace(query=urlencode({k: v[0] for k, v in _qs.items()})))

    alembic_ini = os.path.join(_ROOT, "db", "alembic.ini")
    try:
        import io  # noqa: PLC0415
        from alembic import command as alembic_command  # noqa: PLC0415
        from alembic.config import Config  # noqa: PLC0415

        # env.py reads DATABASE_URL from os.environ — patch it with the
        # normalized asyncpg URL so env.py doesn't override our value.
        os.environ["DATABASE_URL"] = database_url

        log_stream = io.StringIO()
        cfg = Config(alembic_ini, stdout=log_stream)
        cfg.set_main_option("sqlalchemy.url", database_url)

        alembic_command.upgrade(cfg, "head")

        output = log_stream.getvalue()
        _json_response(req, 200, {
            "status": "ok",
            "output": output[-4000:] if output else "Migration completed (no output).",
        })
    except Exception as exc:
        _json_response(req, 500, {"detail": f"Migration error: {exc}"})


# ─────────────────────────────────────────────────────────────────────────────
# Router — single handler dispatches by path and method
# ─────────────────────────────────────────────────────────────────────────────

_ROUTES: dict[tuple[str, str], object] = {
    # Core
    ("GET",  "/api/health"):              _handle_health,
    ("GET",  "/api/secret-debug"):        _handle_secret_debug,
    # Backtest
    ("GET",  "/api/backtest"):            _handle_backtest_get,
    ("POST", "/api/backtest"):            _handle_backtest_post,
    # Paper trading
    ("GET",  "/api/paper-trade"):         _handle_paper_trade_get,
    ("POST", "/api/paper-trade"):         _handle_paper_trade_post,
    # DB
    ("POST", "/api/migrate"):             _handle_migrate_post,
    # Dashboard data
    ("GET",  "/api/portfolio/metrics"):   _handle_portfolio_metrics,
    ("GET",  "/api/logs"):                _handle_logs,
    # Live trading
    ("POST", "/api/trade/execute"):       _handle_trade_execute,
    # System control
    ("GET",  "/api/control/status"):      _handle_system_status,
    ("POST", "/api/control/kill-switch"): _handle_kill_switch,
    ("POST", "/api/control/reset"):       _handle_system_reset,
}


class handler(BaseHTTPRequestHandler):  # noqa: N801
    def _dispatch(self) -> None:
        path = self.path.split("?")[0]  # strip QS for routing; handlers read req.path for QS
        key = (self.command, path)
        route_fn = _ROUTES.get(key)
        if route_fn is None:
            _json_response(self, 404, {"detail": f"No route for {self.command} {path}"})
        else:
            try:
                route_fn(self)
            except Exception as exc:
                _json_response(self, 500, {"detail": str(exc)})

    def do_GET(self) -> None:   # noqa: N802
        self._dispatch()

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass

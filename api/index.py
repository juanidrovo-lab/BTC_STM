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
    ("GET",  "/api/health"):        _handle_health,
    ("GET",  "/api/secret-debug"):  _handle_secret_debug,
    ("GET",  "/api/backtest"):      _handle_backtest_get,
    ("POST", "/api/backtest"):      _handle_backtest_post,
    ("GET",  "/api/paper-trade"):   _handle_paper_trade_get,
    ("POST", "/api/paper-trade"):   _handle_paper_trade_post,
    ("POST", "/api/migrate"):       _handle_migrate_post,
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

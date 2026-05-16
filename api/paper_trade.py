"""Vercel serverless function — POST /api/paper-trade.

Runs one administrative tick of the paper trading engine and returns
event counts.  The actual continuous trading loop runs inside the
orchestrator; this endpoint is for lightweight status checks and
single-tick simulations driven by Vercel Cron or an external scheduler.

POST body (JSON):
    {"session_id": "...", "symbol": "BTCUSDT"}

Response:
    {"status": "ok", "events": <int>}

Errors:
    503 — DATABASE_URL not configured
    400 — missing required fields
    500 — internal error
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):  # noqa: N801
    def do_POST(self) -> None:  # noqa: N802
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            self._respond(
                503,
                {
                    "status": "error",
                    "error": "DATABASE_URL is not configured. Set it in Vercel environment variables.",
                },
            )
            return

        # Parse request body
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            body: dict[str, object] = json.loads(raw_body)
        except json.JSONDecodeError:
            self._respond(400, {"status": "error", "error": "Invalid JSON body."})
            return

        session_id = body.get("session_id")
        symbol = body.get("symbol", "BTCUSDT")

        if not session_id:
            self._respond(400, {"status": "error", "error": "session_id is required."})
            return

        try:
            # Import is deferred so the function can boot without the [db] extras
            # when DATABASE_URL is absent (e.g. in tests).
            from btc_stm.persistence.neon_store import NeonSessionStore  # noqa: PLC0415

            store = NeonSessionStore(database_url=database_url)

            import asyncio  # noqa: PLC0415

            async def _load() -> int:
                try:
                    manifest = await store.load_manifest(str(session_id))
                    return manifest.total_events
                finally:
                    await store.close()

            total_events = asyncio.run(_load())
            self._respond(
                200,
                {
                    "status": "ok",
                    "session_id": session_id,
                    "symbol": symbol,
                    "events": total_events,
                },
            )
        except KeyError:
            self._respond(
                404,
                {"status": "error", "error": f"Session not found: {session_id}"},
            )
        except Exception as exc:  # noqa: BLE001
            self._respond(500, {"status": "error", "error": str(exc)})

    def do_GET(self) -> None:  # noqa: N802
        self._respond(
            200,
            {
                "endpoint": "/api/paper-trade",
                "method": "POST",
                "body": {"session_id": "string (required)", "symbol": "string (default: BTCUSDT)"},
                "response": {"status": "ok", "events": "integer"},
            },
        )

    def _respond(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass

"""Vercel serverless function — GET /api/health."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):  # noqa: N801  (Vercel requires lowercase 'handler')
    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps({"status": "ok", "service": "btc-stm", "version": "0.2.0"})
        encoded = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # suppress default Apache-style access log

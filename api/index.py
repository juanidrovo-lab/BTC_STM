"""Zero-dependency diagnostic — stdlib only, no pip packages."""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):  # noqa: N801
    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps({
            "status": "ok",
            "python": sys.version,
            "path": self.path,
            "trading_mode": os.environ.get("TRADING_MODE", "paper"),
            "db_configured": bool(os.environ.get("DATABASE_URL")),
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass

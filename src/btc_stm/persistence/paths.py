"""Path safety helpers for local persistence."""

from __future__ import annotations

import re
from pathlib import Path


def resolve_safe_path(base_dir: Path, relative_path: str) -> Path:
    resolved_base = base_dir.expanduser().resolve()
    requested = Path(relative_path)
    if requested.is_absolute():
        raise ValueError("relative_path must not be absolute.")

    resolved_path = (resolved_base / requested).resolve()
    if resolved_path != resolved_base and resolved_base not in resolved_path.parents:
        raise ValueError("Resolved path escapes base_dir.")
    return resolved_path


def sanitize_session_id(session_id: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_-]", "_", session_id.strip())
    if not sanitized:
        raise ValueError("session_id must not be empty after sanitization.")
    return sanitized

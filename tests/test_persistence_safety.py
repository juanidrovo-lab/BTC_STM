from pathlib import Path

import pytest

from btc_stm.persistence.paths import resolve_safe_path, sanitize_session_id


def test_resolve_safe_path_rejects_absolute_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="absolute"):
        resolve_safe_path(tmp_path, str((tmp_path / "escape.json").resolve()))


def test_resolve_safe_path_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="escapes"):
        resolve_safe_path(tmp_path, "../escape.json")


def test_resolve_safe_path_allows_nested_relative_path(tmp_path: Path) -> None:
    resolved = resolve_safe_path(tmp_path, "sessions/session-1/manifest.json")

    assert resolved == (tmp_path / "sessions" / "session-1" / "manifest.json").resolve()


def test_sanitize_session_id_cleans_dangerous_characters() -> None:
    assert sanitize_session_id("../bad session!") == "___bad_session_"


def test_sanitize_session_id_rejects_empty_result() -> None:
    with pytest.raises(ValueError, match="empty"):
        sanitize_session_id("   ")


def test_persistence_has_no_network_or_dangerous_patterns() -> None:
    persistence_dir = Path("src/btc_stm/persistence")
    forbidden = (
        "requests",
        "httpx",
        "aiohttp",
        "websockets",
        "socket",
        "api_key",
        "secret",
        "hmac",
        "private",
        "create_order",
        "cancel_order",
        "place_order",
        "def buy",
        "def sell",
        "predict",
        "sklearn",
        "tensorflow",
        "torch",
        "optimiz",
        "pickle",
        "eval(",
    )
    scanned = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in persistence_dir.rglob("*.py")
    )

    assert not any(pattern in scanned for pattern in forbidden)

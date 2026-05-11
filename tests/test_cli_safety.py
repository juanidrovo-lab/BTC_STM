from pathlib import Path


def test_cli_has_no_network_or_dangerous_patterns() -> None:
    cli_dir = Path("src/btc_stm/cli")
    forbidden = (
        "requests",
        "httpx",
        "aiohttp",
        "websockets",
        "socket",
        "api_key",
        "api_secret",
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
    scanned = "\n".join(path.read_text(encoding="utf-8").lower() for path in cli_dir.rglob("*.py"))

    assert not any(pattern in scanned for pattern in forbidden)

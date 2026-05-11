import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from btc_stm.orchestration.models import PaperTradingConfig
from btc_stm.persistence.serialization import (
    read_json,
    to_jsonable,
    write_json_atomic,
    write_jsonl_atomic,
)


def test_to_jsonable_converts_decimal_to_string() -> None:
    assert to_jsonable({"value": Decimal("1.23")}) == {"value": "1.23"}


def test_to_jsonable_converts_datetime_to_iso() -> None:
    timestamp = datetime(2026, 5, 11, 12, 30, tzinfo=UTC)

    assert to_jsonable({"timestamp": timestamp}) == {"timestamp": timestamp.isoformat()}


def test_to_jsonable_converts_pydantic_models() -> None:
    config = PaperTradingConfig(
        symbol="BTCUSDT",
        initial_cash=Decimal("1000"),
        fee_rate_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    payload = to_jsonable(config)

    assert payload["initial_cash"] == "1000"
    assert payload["symbol"] == "BTCUSDT"


def test_to_jsonable_converts_path_to_string(tmp_path: Path) -> None:
    assert to_jsonable(tmp_path) == str(tmp_path)


def test_write_json_atomic_creates_valid_file(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "payload.json"

    write_json_atomic(path, {"value": Decimal("1.23")})

    assert read_json(path) == {"value": "1.23"}


def test_write_jsonl_atomic_creates_valid_json_lines(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"

    write_jsonl_atomic(path, [{"value": Decimal("1")}, {"value": Decimal("2")}])

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows == [{"value": "1"}, {"value": "2"}]


def test_read_json_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_json(tmp_path / "missing.json")


def test_read_json_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{bad", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON"):
        read_json(path)

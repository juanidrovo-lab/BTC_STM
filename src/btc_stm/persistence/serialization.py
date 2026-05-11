"""Safe JSON serialization for local persistence."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return to_jsonable(value.model_dump(mode="python"))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list | tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    return value


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as temp_file:
        temp_path = Path(temp_file.name)
        json.dump(
            to_jsonable(payload),
            temp_file,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        temp_file.write("\n")
    os.replace(temp_path, path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"JSON file does not exist: {path}")
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return payload


def write_jsonl_atomic(path: Path, rows: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as temp_file:
        temp_path = Path(temp_file.name)
        for row in rows:
            temp_file.write(json.dumps(to_jsonable(row), ensure_ascii=False, sort_keys=True))
            temp_file.write("\n")
    os.replace(temp_path, path)

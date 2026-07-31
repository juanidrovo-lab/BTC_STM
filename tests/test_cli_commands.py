from pathlib import Path

import pytest
from pydantic import ValidationError

from btc_stm.cli import commands
from btc_stm.cli.main import run_cli
from btc_stm.settings import Settings


def test_validate_returns_zero_in_safe_paper_mode(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = run_cli(["validate"])

    assert exit_code == 0
    assert "OK: system is in safe paper mode" in capsys.readouterr().out


def test_validate_returns_one_when_settings_are_invalid(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def raise_validation_error() -> Settings:
        raise ValidationError.from_exception_data("Settings", [])

    monkeypatch.setattr(commands, "Settings", raise_validation_error)

    exit_code = run_cli(["validate"])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "ERROR: system settings are invalid or unsafe" in output


def test_validate_error_does_not_print_traceback_or_secrets(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def raise_runtime_error() -> Settings:
        raise RuntimeError("api_secret=unsafe")

    monkeypatch.setattr(commands, "Settings", raise_runtime_error)

    exit_code = run_cli(["validate"])
    output = capsys.readouterr().out.lower()

    assert exit_code == 1
    assert "traceback" not in output
    assert "api_secret" not in output


def test_sessions_list_empty_base_dir_prints_no_sessions(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = run_cli(["sessions", "list", "--base-dir", str(tmp_path)])

    assert exit_code == 0
    assert "No sessions found." in capsys.readouterr().out


def test_sessions_show_missing_session_returns_nonzero(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = run_cli(
        ["sessions", "show", "missing-session", "--base-dir", str(tmp_path)]
    )

    assert exit_code == 1
    assert "ERROR: session not found: missing-session" in capsys.readouterr().out


def test_validate_does_not_call_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network call attempted")

    monkeypatch.setattr("socket.socket", fail_network)

    assert run_cli(["validate"]) == 0

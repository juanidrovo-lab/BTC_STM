from pathlib import Path

import pytest

from btc_stm.cli.main import run_cli


def test_validate_returns_zero_in_safe_paper_mode(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = run_cli(["validate"])

    assert exit_code == 0
    assert "OK: system is in safe paper mode" in capsys.readouterr().out


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

from pathlib import Path

import pytest

from btc_stm.cli.main import run_cli


def test_demo_paper_run_creates_session_and_sessions_list_shows_it(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    demo_exit = run_cli(
        [
            "demo",
            "paper-run",
            "--base-dir",
            str(tmp_path),
            "--session-id",
            "demo-1",
        ]
    )
    demo_output = capsys.readouterr().out

    list_exit = run_cli(["sessions", "list", "--base-dir", str(tmp_path)])
    list_output = capsys.readouterr().out

    assert demo_exit == 0
    assert "session_id: demo-1" in demo_output
    assert "execution_reports: 1" in demo_output
    assert list_exit == 0
    assert "session_id: demo-1" in list_output


def test_demo_paper_run_does_not_overwrite_by_default(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = [
        "demo",
        "paper-run",
        "--base-dir",
        str(tmp_path),
        "--session-id",
        "demo-1",
    ]
    assert run_cli(args) == 0
    capsys.readouterr()

    exit_code = run_cli(args)
    output = capsys.readouterr().out.lower()

    assert exit_code == 1
    assert "error: session already exists: demo-1" in output
    assert "traceback" not in output
    assert "secret" not in output


def test_demo_paper_run_overwrite_flag_allows_overwrite(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = [
        "demo",
        "paper-run",
        "--base-dir",
        str(tmp_path),
        "--session-id",
        "demo-1",
    ]
    assert run_cli(args) == 0
    capsys.readouterr()

    exit_code = run_cli([*args, "--overwrite"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "session_id: demo-1" in output


def test_sessions_show_displays_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_cli(
        [
            "demo",
            "paper-run",
            "--base-dir",
            str(tmp_path),
            "--session-id",
            "demo-1",
        ]
    )
    capsys.readouterr()

    show_exit = run_cli(["sessions", "show", "demo-1", "--base-dir", str(tmp_path)])
    show_output = capsys.readouterr().out

    assert show_exit == 0
    assert "session_id: demo-1" in show_output
    assert "starting_equity:" in show_output
    assert "ending_equity:" in show_output
    assert "total_return_pct:" in show_output
    assert "max_drawdown_pct:" in show_output


def test_demo_paper_run_does_not_create_real_orders(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = run_cli(
        [
            "demo",
            "paper-run",
            "--base-dir",
            str(tmp_path),
            "--session-id",
            "demo-1",
        ]
    )
    output = capsys.readouterr().out.lower()

    assert exit_code == 0
    assert "real order" not in output
    assert "binance" not in output

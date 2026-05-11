from pathlib import Path

import pytest

from btc_stm.cli.demo import build_demo_bars, run_demo_paper_session
from btc_stm.execution.models import ExecutionStatus


def test_build_demo_bars_is_deterministic() -> None:
    bars = build_demo_bars()

    assert len(bars) == 3
    assert [str(bar.close) for bar in bars] == ["100", "105", "110"]
    assert bars[0].symbol == "BTCUSDT"
    assert bars[0].open_time.tzinfo is not None


def test_run_demo_paper_session_persists_result(tmp_path: Path) -> None:
    manifest, result = run_demo_paper_session(tmp_path, "demo-1")

    assert manifest.session_id == "demo-1"
    assert len(result.equity_curve) == 3
    assert result.execution_reports[0].status is ExecutionStatus.FILLED
    assert (tmp_path / manifest.artifact_paths["manifest"]).exists()


def test_run_demo_paper_session_uses_overwrite_false_by_default(tmp_path: Path) -> None:
    run_demo_paper_session(tmp_path, "demo-1")

    with pytest.raises(FileExistsError):
        run_demo_paper_session(tmp_path, "demo-1")


def test_run_demo_paper_session_allows_overwrite_true(tmp_path: Path) -> None:
    run_demo_paper_session(tmp_path, "demo-1")

    manifest, result = run_demo_paper_session(tmp_path, "demo-1", overwrite=True)

    assert manifest.session_id == "demo-1"
    assert len(result.equity_curve) == 3


def test_run_demo_paper_session_sanitizes_session_id(tmp_path: Path) -> None:
    manifest, _result = run_demo_paper_session(tmp_path, "../bad session")

    assert manifest.session_id == "___bad_session"


def test_demo_paper_session_does_not_call_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network call attempted")

    monkeypatch.setattr("socket.socket", fail_network)

    run_demo_paper_session(tmp_path, "demo-no-network")

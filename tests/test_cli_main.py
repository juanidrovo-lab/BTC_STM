from importlib.metadata import version

import pytest

from btc_stm.cli.main import run_cli


def test_run_cli_version_returns_zero_and_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = run_cli(["version"])

    assert exit_code == 0
    assert f"btc-stm {version('btc-stm')}" in capsys.readouterr().out


def test_run_cli_rejects_api_key_flag() -> None:
    with pytest.raises(SystemExit):
        run_cli(["--api-key", "unsafe", "version"])


def test_run_cli_rejects_api_secret_flag() -> None:
    with pytest.raises(SystemExit):
        run_cli(["demo", "paper-run", "--api-secret", "unsafe"])


def test_run_cli_rejects_live_flag() -> None:
    with pytest.raises(SystemExit):
        run_cli(["validate", "--live"])

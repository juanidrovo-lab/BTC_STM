"""CLI command handlers."""

from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from btc_stm.cli.demo import run_demo_paper_session
from btc_stm.cli.formatting import format_demo_result, format_manifest, format_session_summary
from btc_stm.persistence.local_store import LocalSessionStore
from btc_stm.persistence.models import PersistenceConfig
from btc_stm.settings import Settings, TradingMode


def command_version(_args: argparse.Namespace) -> int:
    try:
        package_version = version("btc-stm")
    except PackageNotFoundError:
        package_version = "unknown"
    print(f"btc-stm {package_version}")
    return 0


def command_validate(_args: argparse.Namespace) -> int:
    try:
        settings = Settings()
    except Exception:
        print("ERROR: system settings are invalid or unsafe")
        return 1
    if settings.trading_mode is TradingMode.PAPER and not settings.enable_live_trading:
        print("OK: system is in safe paper mode")
        return 0
    print("ERROR: system is not in safe paper mode")
    return 1


def command_sessions_list(args: argparse.Namespace) -> int:
    store = _store_from_base_dir(args.base_dir)
    sessions = store.list_sessions()
    if not sessions:
        print("No sessions found.")
        return 0
    for index, manifest in enumerate(sessions):
        if index > 0:
            print()
        print(format_manifest(manifest))
    return 0


def command_sessions_show(args: argparse.Namespace) -> int:
    store = _store_from_base_dir(args.base_dir)
    try:
        session = store.load_session_summary(args.session_id)
    except FileNotFoundError:
        print(f"ERROR: session not found: {args.session_id}")
        return 1
    print(format_session_summary(session))
    return 0


def command_demo_paper_run(args: argparse.Namespace) -> int:
    try:
        manifest, result = run_demo_paper_session(
            Path(args.base_dir),
            args.session_id,
            overwrite=args.overwrite,
        )
    except FileExistsError:
        print(f"ERROR: session already exists: {args.session_id}")
        return 1
    print(format_demo_result(manifest, result))
    return 0


def _store_from_base_dir(base_dir: str) -> LocalSessionStore:
    return LocalSessionStore(PersistenceConfig(base_dir=Path(base_dir)))

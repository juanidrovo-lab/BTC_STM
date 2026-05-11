"""Argparse entrypoint for btc-stm."""

from __future__ import annotations

import argparse

from btc_stm.cli.commands import (
    command_demo_paper_run,
    command_sessions_list,
    command_sessions_show,
    command_validate,
    command_version,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="btc-stm")
    subparsers = parser.add_subparsers(dest="command", required=True)

    version_parser = subparsers.add_parser("version")
    version_parser.set_defaults(handler=command_version)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.set_defaults(handler=command_validate)

    sessions_parser = subparsers.add_parser("sessions")
    sessions_subparsers = sessions_parser.add_subparsers(
        dest="sessions_command",
        required=True,
    )

    list_parser = sessions_subparsers.add_parser("list")
    list_parser.add_argument("--base-dir", required=True)
    list_parser.set_defaults(handler=command_sessions_list)

    show_parser = sessions_subparsers.add_parser("show")
    show_parser.add_argument("session_id")
    show_parser.add_argument("--base-dir", required=True)
    show_parser.set_defaults(handler=command_sessions_show)

    demo_parser = subparsers.add_parser("demo")
    demo_subparsers = demo_parser.add_subparsers(dest="demo_command", required=True)

    paper_run_parser = demo_subparsers.add_parser("paper-run")
    paper_run_parser.add_argument("--base-dir", required=True)
    paper_run_parser.add_argument("--session-id", required=True)
    paper_run_parser.set_defaults(handler=command_demo_paper_run)

    return parser


def run_cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


def main() -> int:
    return run_cli()

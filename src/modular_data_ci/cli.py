"""Command line entry point.

    modular-data-ci run --config modular-data-ci.yml --report report.json

Exit codes: 0 all required checks passed, 1 a required check failed or errored,
2 invalid arguments or configuration.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from modular_data_ci import __version__
from modular_data_ci.config import load_config
from modular_data_ci.engine import Engine
from modular_data_ci.errors import ModularDataCIError
from modular_data_ci.reporting import render_terminal, write_json
from modular_data_ci.reporting.terminal import use_color
from modular_data_ci.results import EXIT_OK, EXIT_USAGE_ERROR


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modular-data-ci",
        description="Configuration-driven data quality checks for CI.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="<command>")

    run = commands.add_parser("run", help="run the configured checks")
    run.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("modular-data-ci.yml"),
        help="configuration file (default: modular-data-ci.yml)",
    )
    run.add_argument("--report", type=Path, help="write a JSON report to this path")
    run.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="colorize output (default: auto; honours NO_COLOR)",
    )
    run.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="NAME",
        help="run only this check (repeatable)",
    )
    run.add_argument(
        "--skip",
        action="append",
        default=[],
        metavar="NAME",
        help="leave out this check (repeatable)",
    )
    run.add_argument(
        "--module",
        action="append",
        default=[],
        metavar="MODULE",
        help="run only checks of this module (repeatable)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return EXIT_OK
    try:
        return _run(args)
    except ModularDataCIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR


def _run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    report = Engine().run(
        config,
        only=_split(args.only),
        skip=_split(args.skip),
        modules=_split(args.module),
        config_path=str(args.config),
    )
    color = use_color(args.color, sys.stdout)
    sys.stdout.write(render_terminal(report, color=color))
    if args.report:
        write_json(report, args.report)
    return report.exit_code


def _split(values: Sequence[str]) -> list[str]:
    """Accept both ``--only a --only b`` and ``--only a,b``."""
    return [part.strip() for value in values for part in value.split(",") if part.strip()]

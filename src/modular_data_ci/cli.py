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
    report = Engine().run(config, config_path=str(args.config))
    sys.stdout.write(render_terminal(report))
    if args.report:
        write_json(report, args.report)
    return report.exit_code

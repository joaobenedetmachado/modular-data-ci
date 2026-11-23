"""Command line entry point.

    modular-data-ci run --config modular-data-ci.yml --report report.json

Exit codes: 0 all required checks passed, 1 a required check failed or errored,
2 invalid arguments or configuration.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from modular_data_ci import __version__
from modular_data_ci.config import load_config
from modular_data_ci.engine import Engine
from modular_data_ci.errors import ConfigError, ModularDataCIError
from modular_data_ci.reporting import render_terminal, write_json
from modular_data_ci.reporting.terminal import use_color
from modular_data_ci.results import EXIT_OK, EXIT_USAGE_ERROR

DEFAULT_CONFIG_NAMES = ("modular-data-ci.yml", "modular-data-ci.yaml", ".modular-data-ci.yml")
CONFIG_ENV_VAR = "MDCI_CONFIG"


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
        help=f"configuration file (default: ${CONFIG_ENV_VAR}, then {DEFAULT_CONFIG_NAMES[0]})",
    )
    run.add_argument("--report", type=Path, help="write a JSON report to this path")
    run.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="colorize output (default: auto; honours NO_COLOR)",
    )
    noise = run.add_mutually_exclusive_group()
    noise.add_argument(
        "-v", "--verbose", action="count", default=0, help="show check details (-vv: all)"
    )
    noise.add_argument("-q", "--quiet", action="store_true", help="only list failing checks")
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
    args.config = find_config(args.config)
    config = load_config(args.config)
    report = Engine().run(
        config,
        only=_split(args.only),
        skip=_split(args.skip),
        modules=_split(args.module),
        config_path=str(args.config),
    )
    color = use_color(args.color, sys.stdout)
    sys.stdout.write(
        render_terminal(report, color=color, verbosity=-1 if args.quiet else args.verbose)
    )
    if args.report:
        write_json(report, args.report)
    return report.exit_code


def _split(values: Sequence[str]) -> list[str]:
    """Accept both ``--only a --only b`` and ``--only a,b``."""
    return [part.strip() for value in values for part in value.split(",") if part.strip()]


def find_config(explicit: Path | None, cwd: Path | None = None) -> Path:
    """Explicit path, then ``$MDCI_CONFIG``, then the first default name that exists."""
    if explicit is not None:
        return explicit
    if env_path := os.environ.get(CONFIG_ENV_VAR):
        return Path(env_path)
    base = cwd or Path.cwd()
    for name in DEFAULT_CONFIG_NAMES:
        if (base / name).is_file():
            return Path(name)
    raise ConfigError(
        DEFAULT_CONFIG_NAMES[0],
        [f"file not found (also looked for {', '.join(DEFAULT_CONFIG_NAMES[1:])}; use --config)"],
    )

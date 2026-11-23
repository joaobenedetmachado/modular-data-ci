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
from modular_data_ci.registry import ModuleRegistry, resolve_checks
from modular_data_ci.reporting import render_terminal, write_json
from modular_data_ci.reporting.github import (
    append_step_summary,
    in_github_actions,
    render_annotations,
)
from modular_data_ci.reporting.junit import write_junit
from modular_data_ci.reporting.terminal import use_color
from modular_data_ci.results import EXIT_OK, EXIT_USAGE_ERROR

DEFAULT_CONFIG_NAMES = ("modular-data-ci.yml", "modular-data-ci.yaml", ".modular-data-ci.yml")
CONFIG_ENV_VAR = "MDCI_CONFIG"
EXIT_INTERRUPTED = 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modular-data-ci",
        description="Configuration-driven data quality checks for CI.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="<command>")

    run = commands.add_parser("run", help="run the configured checks")
    _add_config_argument(run)
    run.add_argument("--report", type=Path, help="write a JSON report to this path")
    run.add_argument("--junit", type=Path, help="write a JUnit XML report to this path")
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
    validate = commands.add_parser(
        "validate", help="check the configuration without connecting to the data source"
    )
    _add_config_argument(validate)

    listing = commands.add_parser("list", help="list the configured checks")
    _add_config_argument(listing)

    commands.add_parser("modules", help="list available validation modules (built-in and plugins)")
    return parser


def _add_config_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        help=f"configuration file (default: ${CONFIG_ENV_VAR}, then {DEFAULT_CONFIG_NAMES[0]})",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return EXIT_OK
    handlers = {"run": _run, "validate": _validate, "list": _list, "modules": _modules}
    try:
        return handlers[args.command](args)
    except ModularDataCIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return EXIT_INTERRUPTED


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
    if in_github_actions():
        sys.stdout.write(render_annotations(report, str(args.config)))
        append_step_summary(report)
    try:
        if args.report:
            write_json(report, args.report)
        if args.junit:
            write_junit(report, args.junit)
    except OSError as exc:
        print(f"error: cannot write report: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    return report.exit_code


def _split(values: Sequence[str]) -> list[str]:
    """Accept both ``--only a --only b`` and ``--only a,b``."""
    return [part.strip() for value in values for part in value.split(",") if part.strip()]


def _validate(args: argparse.Namespace) -> int:
    path = find_config(args.config)
    config = load_config(path)
    resolve_checks(config, ModuleRegistry.default(), source=str(path))
    enabled = sum(1 for check in config.checks if check.enabled)
    print(f"{path}: OK ({len(config.checks)} checks, {enabled} enabled)")
    return EXIT_OK


def _list(args: argparse.Namespace) -> int:
    config = load_config(find_config(args.config))
    rows = [("NAME", "MODULE", "ENABLED", "REQUIRED", "DESCRIPTION")]
    for check in config.checks:
        enabled = check.enabled and config.module_enabled(check.module)
        rows.append(
            (
                check.name,
                check.module,
                "yes" if enabled else "no",
                "yes" if check.required else "no",
                check.description or "",
            )
        )
    widths = [max(len(row[i]) for row in rows) for i in range(4)]
    for row in rows:
        cells = [cell.ljust(width) for cell, width in zip(row[:4], widths, strict=True)]
        print("  ".join([*cells, row[4]]).rstrip())
    return EXIT_OK


def _modules(args: argparse.Namespace) -> int:
    registry = ModuleRegistry.default()
    width = max(len(name) for name in registry.names())
    for name in registry.names():
        module = registry.get(name)
        print(f"{name.ljust(width)}  {type(module).summary()}".rstrip())
    return EXIT_OK


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

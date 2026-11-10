"""Command line entry point.

Day 1 only exposes ``--version`` and help. The ``run`` command arrives on Day 5.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from modular_data_ci import __version__
from modular_data_ci.results import EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modular-data-ci",
        description="Configuration-driven data quality checks for CI.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return EXIT_OK

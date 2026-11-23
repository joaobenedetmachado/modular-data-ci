"""Readable terminal summary of a run."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TextIO

from modular_data_ci.results import CheckResult, CheckStatus, RunReport

SYMBOLS = {
    CheckStatus.SUCCESS: "PASS",
    CheckStatus.FAILURE: "FAIL",
    CheckStatus.SKIPPED: "SKIP",
    CheckStatus.ERROR: "ERR ",
}
COLORS = {
    CheckStatus.SUCCESS: "32",  # green
    CheckStatus.FAILURE: "31",  # red
    CheckStatus.SKIPPED: "33",  # yellow
    CheckStatus.ERROR: "35",  # magenta
}
_DIM = "2"
_BOLD = "1"


def use_color(mode: str, stream: TextIO, env: Mapping[str, str] | None = None) -> bool:
    """Resolve ``--color auto|always|never``. ``auto`` honours NO_COLOR and FORCE_COLOR."""
    env = os.environ if env is None else env
    if mode == "always":
        return True
    if mode == "never" or "NO_COLOR" in env:
        return False
    if env.get("FORCE_COLOR"):
        return True
    return hasattr(stream, "isatty") and stream.isatty()


class _Style:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def __call__(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text


def _line(result: CheckResult, style: _Style) -> str:
    label = style(SYMBOLS[result.status], COLORS[result.status])
    optional = style(" (optional)", _DIM) if not result.required else ""
    text = f"  {label}  {result.name} {style(f'[{result.module}]', _DIM)}{optional}"
    if result.message:
        text += f" - {result.message}"
    return text


def _details(result: CheckResult, style: _Style) -> list[str]:
    return [style(f"        {key}: {value}", _DIM) for key, value in result.details.items()]


def render_terminal(report: RunReport, *, color: bool = False, verbosity: int = 0) -> str:
    """Return the terminal summary.

    ``verbosity`` -1 lists only failing and erroring checks, 0 lists every check,
    1 also prints the details of checks that did not succeed, 2 prints all details.
    """
    style = _Style(color)
    lines = [style(f"modular-data-ci {report.tool_version}", _BOLD)]
    if report.config_path:
        lines.append(style(f"config: {report.config_path}", _DIM))
    lines.append("")
    for result in report.results:
        problem = result.status in (CheckStatus.FAILURE, CheckStatus.ERROR)
        if verbosity < 0 and not problem:
            continue
        lines.append(_line(result, style))
        if verbosity >= 2 or (verbosity == 1 and result.status is not CheckStatus.SUCCESS):
            lines.extend(_details(result, style))
    summary = report.summary
    lines.append("")
    lines.append(
        f"{summary.total} checks: {summary.success} passed, {summary.failure} failed, "
        f"{summary.error} errors, {summary.skipped} skipped"
    )
    if report.passed:
        lines.append(style("RESULT: PASSED", f"{_BOLD};32"))
    else:
        lines.append(style(f"RESULT: FAILED ({summary.blocking} blocking)", f"{_BOLD};31"))
    return "\n".join(lines) + "\n"

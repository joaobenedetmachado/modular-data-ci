"""Readable terminal summary of a run."""

from __future__ import annotations

from modular_data_ci.results import CheckResult, CheckStatus, RunReport

SYMBOLS = {
    CheckStatus.SUCCESS: "PASS",
    CheckStatus.FAILURE: "FAIL",
    CheckStatus.SKIPPED: "SKIP",
    CheckStatus.ERROR: "ERR ",
}


def _line(result: CheckResult) -> str:
    label = SYMBOLS[result.status]
    optional = "" if result.required else " (optional)"
    text = f"  {label}  {result.name} [{result.module}]{optional}"
    if result.message:
        text += f" - {result.message}"
    return text


def render_terminal(report: RunReport) -> str:
    """Return the full terminal summary, one line per check plus a totals line."""
    lines = [f"modular-data-ci {report.tool_version}"]
    if report.config_path:
        lines.append(f"config: {report.config_path}")
    lines.append("")
    lines.extend(_line(result) for result in report.results)
    summary = report.summary
    lines.append("")
    lines.append(
        f"{summary.total} checks: {summary.success} passed, {summary.failure} failed, "
        f"{summary.error} errors, {summary.skipped} skipped"
    )
    lines.append(
        "RESULT: PASSED" if report.passed else f"RESULT: FAILED ({summary.blocking} blocking)"
    )
    return "\n".join(lines) + "\n"

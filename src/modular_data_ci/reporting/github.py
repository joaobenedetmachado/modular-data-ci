"""GitHub Actions output: workflow annotations and the job step summary."""

from __future__ import annotations

import os
from collections.abc import Mapping

from modular_data_ci.results import CheckResult, CheckStatus, RunReport


def in_github_actions(env: Mapping[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    return env.get("GITHUB_ACTIONS") == "true"


def _escape_data(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(text: str) -> str:
    return _escape_data(text).replace(":", "%3A").replace(",", "%2C")


def _annotation(result: CheckResult) -> str | None:
    if result.status not in (CheckStatus.FAILURE, CheckStatus.ERROR):
        return None
    level = "error" if result.required else "warning"
    title = f"{result.name} ({result.status.value})"
    message = result.message or result.status.value
    return f"::{level} title={_escape_property(title)}::{_escape_data(message)}"


def render_annotations(report: RunReport, config_path: str | None = None) -> str:
    """Workflow commands that show failing checks in the Actions UI.

    Required checks become ``::error``, optional ones ``::warning``.
    """
    lines = [line for result in report.results if (line := _annotation(result))]
    if config_path and lines:
        prefix = f"file={_escape_property(config_path)},"
        lines = [line.replace(" title=", f" {prefix}title=", 1) for line in lines]
    return "".join(f"{line}\n" for line in lines)


_STATUS_ICONS = {
    CheckStatus.SUCCESS: "✅",
    CheckStatus.FAILURE: "❌",
    CheckStatus.SKIPPED: "⏭️",
    CheckStatus.ERROR: "⚠️",
}


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_step_summary(report: RunReport) -> str:
    """Markdown table for ``$GITHUB_STEP_SUMMARY``."""
    summary = report.summary
    verdict = "passed" if report.passed else f"failed ({summary.blocking} blocking)"
    lines = [
        f"### Modular Data CI: {verdict}",
        "",
        f"{summary.total} checks: {summary.success} passed, {summary.failure} failed, "
        f"{summary.error} errors, {summary.skipped} skipped",
        "",
        "| Status | Check | Module | Required | Message |",
        "|---|---|---|---|---|",
    ]
    for result in report.results:
        lines.append(
            f"| {_STATUS_ICONS[result.status]} {result.status.value} | `{_cell(result.name)}` "
            f"| {result.module} | {'yes' if result.required else 'no'} "
            f"| {_cell(result.message)} |"
        )
    return "\n".join(lines) + "\n"


def append_step_summary(report: RunReport, env: Mapping[str, str] | None = None) -> bool:
    """Append the summary to ``$GITHUB_STEP_SUMMARY`` when set. Returns True if written."""
    env = os.environ if env is None else env
    path = env.get("GITHUB_STEP_SUMMARY")
    if not path:
        return False
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(render_step_summary(report))
    return True

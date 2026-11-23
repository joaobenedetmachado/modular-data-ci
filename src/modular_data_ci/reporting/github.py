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

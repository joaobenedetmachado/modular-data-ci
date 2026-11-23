"""JUnit XML report, understood by most CI systems and test dashboards."""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

from modular_data_ci.results import CheckStatus, RunReport


def render_junit(report: RunReport) -> str:
    summary = report.summary
    duration = (report.finished_at - report.started_at).total_seconds()
    suite = ET.Element(
        "testsuite",
        name="modular-data-ci",
        tests=str(summary.total),
        failures=str(summary.failure),
        errors=str(summary.error),
        skipped=str(summary.skipped),
        time=f"{duration:.3f}",
        timestamp=report.started_at.isoformat(),
    )
    for result in report.results:
        case = ET.SubElement(
            suite,
            "testcase",
            classname=result.module,
            name=result.name,
            time=f"{result.duration_ms / 1000:.3f}",
        )
        message = result.message or result.status.value
        if result.status is CheckStatus.FAILURE:
            tag = "failure"
        elif result.status is CheckStatus.ERROR:
            tag = "error"
        elif result.status is CheckStatus.SKIPPED:
            ET.SubElement(case, "skipped", message=message)
            continue
        else:
            continue
        if not result.required:
            message = f"[optional] {message}"
        element = ET.SubElement(case, tag, message=message, type=result.status.value)
        if result.details:
            element.text = json.dumps(result.details, indent=2, default=str)
    ET.indent(suite)
    return ET.tostring(suite, encoding="unicode", xml_declaration=True) + "\n"


def write_junit(report: RunReport, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_junit(report), encoding="utf-8")
    return path

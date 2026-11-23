"""Machine-readable JSON report."""

from __future__ import annotations

import json
from pathlib import Path

from modular_data_ci.results import RunReport

REPORT_SCHEMA_VERSION = 1


def render_json(report: RunReport, *, indent: int | None = 2) -> str:
    """Serialize the report, including ``summary`` and ``passed``."""
    payload = report.model_dump(mode="json")
    return _dumps({"schema_version": REPORT_SCHEMA_VERSION, **payload}, indent)


def write_json(report: RunReport, path: str | Path) -> Path:
    """Write the JSON report, creating parent directories as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_json(report) + "\n", encoding="utf-8")
    return path


def _dumps(data: object, indent: int | None) -> str:
    return json.dumps(data, indent=indent, ensure_ascii=False)

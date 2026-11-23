import json
from datetime import datetime, timezone

from modular_data_ci.reporting import render_json, write_json
from modular_data_ci.results import CheckResult, CheckStatus, RunReport

T = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
REPORT = RunReport(
    tool_version="1.2.3",
    started_at=T,
    finished_at=T,
    config_path="cfg.yml",
    results=[CheckResult(name="a", module="schema", status=CheckStatus.FAILURE, message="x")],
)


def test_render_json_has_summary_and_schema_version():
    data = json.loads(render_json(REPORT))
    assert data["schema_version"] == 1
    assert data["passed"] is False
    assert data["summary"]["failure"] == 1
    assert data["results"][0]["status"] == "failure"
    assert data["started_at"] == "2026-03-10T12:00:00Z"


def test_write_json_creates_directories(tmp_path):
    path = write_json(REPORT, tmp_path / "out" / "report.json")
    assert json.loads(path.read_text())["config_path"] == "cfg.yml"

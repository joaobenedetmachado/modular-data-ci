from datetime import datetime, timezone
from xml.etree import ElementTree as ET

from modular_data_ci.reporting.junit import render_junit, write_junit
from modular_data_ci.results import CheckResult, CheckStatus, RunReport

T = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
REPORT = RunReport(
    tool_version="1",
    started_at=T,
    finished_at=T,
    results=[
        CheckResult(name="ok", module="schema", status=CheckStatus.SUCCESS, duration_ms=12),
        CheckResult(
            name="bad",
            module="custom_sql",
            status=CheckStatus.FAILURE,
            message="x",
            details={"value": 3},
        ),
        CheckResult(name="err", module="custom_sql", status=CheckStatus.ERROR, required=False),
        CheckResult(name="skip", module="schema", status=CheckStatus.SKIPPED, message="off"),
    ],
)


def test_junit_structure():
    suite = ET.fromstring(render_junit(REPORT).split("?>", 1)[1])
    assert suite.attrib["tests"] == "4"
    assert suite.attrib["failures"] == "1"
    assert suite.attrib["errors"] == "1"
    cases = {case.attrib["name"]: case for case in suite}
    assert cases["ok"].attrib["time"] == "0.012"
    assert list(cases["ok"]) == []
    assert cases["bad"].find("failure").attrib["message"] == "x"
    assert '"value": 3' in cases["bad"].find("failure").text
    assert cases["err"].find("error").attrib["message"] == "[optional] error"
    assert cases["skip"].find("skipped").attrib["message"] == "off"


def test_write_junit(tmp_path):
    assert write_junit(REPORT, tmp_path / "a" / "j.xml").read_text().startswith("<?xml")

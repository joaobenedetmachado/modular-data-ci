import json
from datetime import datetime, timezone

import pytest

from modular_data_ci.results import (
    EXIT_CHECKS_FAILED,
    EXIT_OK,
    CheckOutcome,
    CheckResult,
    CheckStatus,
    RunReport,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _result(name: str, status: CheckStatus, required: bool = True) -> CheckResult:
    return CheckResult(name=name, module="dummy", status=status, required=required)


def _report(*results: CheckResult) -> RunReport:
    return RunReport(tool_version="test", started_at=T0, finished_at=T0, results=list(results))


def test_outcome_factories_set_status_and_details():
    outcome = CheckOutcome.failure("too old", age_seconds=90)
    assert outcome.status is CheckStatus.FAILURE
    assert outcome.message == "too old"
    assert outcome.details == {"age_seconds": 90}


@pytest.mark.parametrize(
    ("status", "required", "blocking"),
    [
        (CheckStatus.SUCCESS, True, False),
        (CheckStatus.SKIPPED, True, False),
        (CheckStatus.FAILURE, True, True),
        (CheckStatus.ERROR, True, True),
        (CheckStatus.FAILURE, False, False),
        (CheckStatus.ERROR, False, False),
    ],
)
def test_blocking_depends_on_status_and_required(status, required, blocking):
    assert _result("c", status, required).blocking is blocking


def test_empty_report_passes():
    report = _report()
    assert report.passed
    assert report.exit_code == EXIT_OK


def test_optional_failure_does_not_fail_run():
    report = _report(
        _result("a", CheckStatus.SUCCESS),
        _result("b", CheckStatus.FAILURE, required=False),
    )
    assert report.passed
    assert report.exit_code == EXIT_OK


def test_required_error_fails_run_and_summary_counts():
    report = _report(
        _result("a", CheckStatus.SUCCESS),
        _result("b", CheckStatus.ERROR),
        _result("c", CheckStatus.SKIPPED),
        _result("d", CheckStatus.FAILURE, required=False),
    )
    assert not report.passed
    assert report.exit_code == EXIT_CHECKS_FAILED
    summary = report.summary
    assert (summary.total, summary.success, summary.failure, summary.skipped, summary.error) == (
        4,
        1,
        1,
        1,
        1,
    )
    assert summary.blocking == 1


def test_report_json_contains_statuses_summary_and_passed():
    report = _report(_result("a", CheckStatus.FAILURE))
    data = json.loads(report.model_dump_json())
    assert data["passed"] is False
    assert data["summary"]["failure"] == 1
    assert data["results"][0]["status"] == "failure"

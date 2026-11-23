from datetime import datetime, timezone

from modular_data_ci.reporting import render_terminal
from modular_data_ci.results import CheckResult, CheckStatus, RunReport

T = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def report(*results):
    return RunReport(tool_version="1.2.3", started_at=T, finished_at=T, results=list(results))


def result(name, status, required=True, message=""):
    return CheckResult(
        name=name, module="custom_sql", status=status, required=required, message=message
    )


def test_passing_run():
    text = render_terminal(report(result("a", CheckStatus.SUCCESS, message="value 1")))
    assert "PASS  a [custom_sql] - value 1" in text
    assert "1 checks: 1 passed" in text
    assert text.endswith("RESULT: PASSED\n")


def test_failing_run_counts_blocking():
    text = render_terminal(
        report(
            result("a", CheckStatus.FAILURE, message="bad"),
            result("b", CheckStatus.ERROR, required=False),
            result("c", CheckStatus.SKIPPED),
        )
    )
    assert "FAIL  a" in text
    assert "ERR   b [custom_sql] (optional)" in text
    assert "SKIP  c" in text
    assert "RESULT: FAILED (1 blocking)" in text

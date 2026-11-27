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
    assert "skipped in 0.00s" in text
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


class Tty:
    def isatty(self):
        return True


def test_color_codes_only_when_enabled():
    r = report(result("a", CheckStatus.SUCCESS))
    assert "\033[" not in render_terminal(r)
    assert "\033[32mPASS" in render_terminal(r, color=True)


def test_use_color_modes():
    from modular_data_ci.reporting.terminal import use_color

    assert use_color("always", object(), env={"NO_COLOR": "1"})
    assert not use_color("never", Tty(), env={})
    assert not use_color("auto", Tty(), env={"NO_COLOR": ""})
    assert use_color("auto", object(), env={"FORCE_COLOR": "1"})
    assert use_color("auto", Tty(), env={})
    assert not use_color("auto", object(), env={})


def test_verbosity_levels():
    ok = CheckResult(name="ok", module="m", status=CheckStatus.SUCCESS, details={"v": 1})
    bad = CheckResult(name="bad", module="m", status=CheckStatus.FAILURE, details={"v": 2})
    r = report(ok, bad)
    quiet = render_terminal(r, verbosity=-1)
    assert "ok [m]" not in quiet
    assert "bad [m]" in quiet
    assert "v: " not in render_terminal(r)
    one = render_terminal(r, verbosity=1)
    assert "v: 2" in one
    assert "v: 1" not in one
    assert "v: 1" in render_terminal(r, verbosity=2)

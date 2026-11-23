from datetime import datetime, timezone

from modular_data_ci.reporting.github import in_github_actions, render_annotations
from modular_data_ci.results import CheckResult, CheckStatus, RunReport

T = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def report(*results):
    return RunReport(tool_version="1", started_at=T, finished_at=T, results=list(results))


def test_in_github_actions():
    assert in_github_actions({"GITHUB_ACTIONS": "true"})
    assert not in_github_actions({})


def test_annotations_for_failures_only():
    text = render_annotations(
        report(
            CheckResult(name="ok", module="m", status=CheckStatus.SUCCESS),
            CheckResult(name="a", module="m", status=CheckStatus.FAILURE, message="50%\nlow"),
            CheckResult(name="b", module="m", status=CheckStatus.ERROR, required=False),
        )
    )
    assert text.splitlines() == [
        "::error title=a (failure)::50%25%0Alow",
        "::warning title=b (error)::error",
    ]


def test_annotations_point_at_config_file():
    text = render_annotations(
        report(CheckResult(name="a", module="m", status=CheckStatus.FAILURE)), "ci/c.yml"
    )
    assert text.startswith("::error file=ci/c.yml,title=a (failure)::")


def test_step_summary_table(tmp_path):
    from modular_data_ci.reporting.github import append_step_summary

    r = report(CheckResult(name="a|b", module="m", status=CheckStatus.FAILURE, message="x"))
    target = tmp_path / "summary.md"
    assert append_step_summary(r, {"GITHUB_STEP_SUMMARY": str(target)})
    text = target.read_text()
    assert "### Modular Data CI: failed (1 blocking)" in text
    assert "| ❌ failure | `a\\|b` | m | yes | x |" in text
    assert not append_step_summary(r, {})

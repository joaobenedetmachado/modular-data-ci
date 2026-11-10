from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from modular_data_ci.config import parse_config
from modular_data_ci.engine import Engine
from modular_data_ci.errors import ConfigError, DataSourceError, SelectionError
from modular_data_ci.modules import ModuleParams, ValidationModule
from modular_data_ci.registry import ModuleRegistry
from modular_data_ci.results import EXIT_CHECKS_FAILED, EXIT_OK, CheckOutcome, CheckStatus
from tests.fakes import FakeSource

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)


class ExpectParams(ModuleParams):
    result: str = "success"
    """success | failure | raise | bad_return | details"""


class ExpectModule(ValidationModule[ExpectParams]):
    """Test module whose behavior is chosen in the config."""

    name = "expect"
    params_model = ExpectParams

    def run(self, params, context):
        if params.result == "raise":
            raise RuntimeError("boom")
        if params.result == "bad_return":
            return {"status": "success"}
        if params.result == "details":
            return CheckOutcome.success("ok", at=context.now, amount=Decimal("1.5"), obj=object())
        if params.result == "now":
            return CheckOutcome.success(context.now.isoformat())
        return CheckOutcome(status=CheckStatus(params.result), message=params.result)


def _config(checks: str, modules: str = ""):
    return parse_config(
        f"connection: {{type: duckdb}}\n{modules}checks:\n{checks}", env={}, source="t.yml"
    )


def _engine(source=None, env=None, factory=None):
    source = source if source is not None else FakeSource(True)
    return Engine(
        ModuleRegistry([ExpectModule]),
        source_factory=factory or (lambda config: source),
        clock=lambda: NOW,
        env=env or {},
    )


def _statuses(report):
    return {r.name: r.status.value for r in report.results}


def test_successful_run():
    report = _engine().run(_config("  - {name: a, module: expect}"), config_path="t.yml")
    assert report.passed
    assert report.exit_code == EXIT_OK
    assert report.config_path == "t.yml"
    (result,) = report.results
    assert (result.name, result.module, result.status) == ("a", "expect", CheckStatus.SUCCESS)
    assert result.duration_ms >= 0


def test_failure_fails_the_run_but_later_checks_still_run():
    config = _config(
        "  - {name: a, module: expect, result: failure}\n  - {name: b, module: expect}"
    )
    report = _engine().run(config)
    assert _statuses(report) == {"a": "failure", "b": "success"}
    assert report.exit_code == EXIT_CHECKS_FAILED


def test_optional_failure_does_not_fail_the_run():
    report = _engine().run(
        _config("  - {name: a, module: expect, result: failure, required: false}")
    )
    assert report.passed


def test_module_exception_becomes_error():
    report = _engine().run(_config("  - {name: a, module: expect, result: raise}"))
    (result,) = report.results
    assert result.status is CheckStatus.ERROR
    assert result.message == "RuntimeError: boom"
    assert result.details == {"exception_type": "RuntimeError"}
    assert not report.passed


def test_wrong_return_type_becomes_error():
    (result,) = _engine().run(_config("  - {name: a, module: expect, result: bad_return}")).results
    assert result.status is CheckStatus.ERROR
    assert "returned dict, expected CheckOutcome" in result.message


def test_details_are_made_json_safe():
    report = _engine().run(_config("  - {name: a, module: expect, result: details}"))
    details = report.results[0].details
    assert details["at"] == "2026-03-01T12:00:00Z"
    assert details["amount"] == "1.5"
    assert isinstance(details["obj"], str)
    report.model_dump_json()  # must not raise


def test_modules_receive_the_run_clock():
    (result,) = _engine().run(_config("  - {name: a, module: expect, result: now}")).results
    assert result.message == NOW.isoformat()


def test_naive_clock_is_rejected():
    engine = Engine(ModuleRegistry([ExpectModule]), clock=lambda: datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="timezone-aware"):
        engine.run(_config("  - {name: a, module: expect}"))


def test_finished_at_comes_from_clock():
    times = iter([NOW, NOW + timedelta(seconds=3)])
    engine = Engine(
        ModuleRegistry([ExpectModule]),
        source_factory=lambda c: FakeSource(),
        clock=lambda: next(times),
        env={},
    )
    report = engine.run(_config("  - {name: a, module: expect}"))
    assert report.finished_at - report.started_at == timedelta(seconds=3)


# --- skipping, when, dependencies -------------------------------------------


def test_disabled_check_and_module_are_reported_skipped():
    config = _config(
        "  - {name: a, module: expect, enabled: false}\n  - {name: b, module: expect}",
    )
    report = _engine().run(config)
    assert _statuses(report) == {"a": "skipped", "b": "success"}
    assert report.results[0].message == "disabled in config"

    module_off = _config(
        "  - {name: a, module: expect}", modules="modules: {expect: {enabled: false}}\n"
    )
    (result,) = _engine().run(module_off).results
    assert result.status is CheckStatus.SKIPPED
    assert result.message == "module 'expect' is disabled in config"


def test_failed_dependency_skips_dependent_check():
    config = _config(
        "  - {name: a, module: expect, result: failure}\n"
        "  - {name: b, module: expect, when: {depends_on: a}}\n"
        "  - {name: c, module: expect, when: {depends_on: b}}\n"
    )
    report = _engine().run(config)
    assert _statuses(report) == {"a": "failure", "b": "skipped", "c": "skipped"}
    assert report.results[1].message == "dependency 'a' ended with failure"
    assert report.results[2].message == "dependency 'b' ended with skipped"


def test_dependency_filtered_out_by_cli_skips_dependent():
    config = _config(
        "  - {name: a, module: expect}\n  - {name: b, module: expect, when: {depends_on: a}}"
    )
    report = _engine().run(config, only=["b"])
    assert _statuses(report) == {"b": "skipped"}
    assert report.results[0].message == "dependency 'a' was not run"


def test_env_condition_uses_engine_env():
    config = _config("  - {name: a, module: expect, when: {env: {TARGET: prod}}}")
    assert _statuses(_engine(env={"TARGET": "prod"}).run(config)) == {"a": "success"}
    assert _statuses(_engine(env={"TARGET": "dev"}).run(config)) == {"a": "skipped"}


def test_when_sql_uses_the_source():
    config = _config("  - {name: a, module: expect, when: {sql: SELECT has_rows}}")
    assert _statuses(_engine(FakeSource(False)).run(config)) == {"a": "skipped"}
    assert _statuses(_engine(FakeSource(1)).run(config)) == {"a": "success"}


def test_when_sql_failure_is_an_error():
    def handler(sql):
        raise RuntimeError("no such table: x")

    config = _config("  - {name: a, module: expect, when: {sql: SELECT 1 FROM x}}")
    (result,) = _engine(FakeSource(handler=handler)).run(config).results
    assert result.status is CheckStatus.ERROR
    assert result.message == "when condition failed: RuntimeError: no such table: x"


# --- filters ----------------------------------------------------------------


def test_cli_filters_remove_checks_from_report():
    config = _config("  - {name: a, module: expect}\n  - {name: b, module: expect}")
    assert _statuses(_engine().run(config, skip=["a"])) == {"b": "success"}
    with pytest.raises(SelectionError):
        _engine().run(config, only=["zzz"])


# --- resolution and data source ---------------------------------------------


def test_invalid_params_stop_the_run_before_connecting():
    opened = []
    engine = _engine(factory=lambda c: opened.append(c) or FakeSource())
    with pytest.raises(ConfigError, match=r"checks\[0\] \(a\)\.unknown_key: unknown key"):
        engine.run(_config("  - {name: a, module: expect, unknown_key: 1}"))
    assert opened == []


def test_disabled_checks_are_resolved_too():
    with pytest.raises(ConfigError, match="unknown module 'nope'"):
        _engine().run(_config("  - {name: a, module: nope, enabled: false}"))


def test_source_not_opened_when_nothing_runs():
    opened = []
    engine = _engine(factory=lambda c: opened.append(c) or FakeSource())
    report = engine.run(_config("  - {name: a, module: expect, enabled: false}"))
    assert opened == []
    assert report.passed


def test_source_is_closed_after_run():
    source = FakeSource()
    _engine(source).run(_config("  - {name: a, module: expect}"))
    assert source.closed


def test_connection_failure_marks_running_checks_as_errors():
    def fail(config):
        raise DataSourceError("DuckDB database file not found: x.duckdb")

    config = _config("  - {name: a, module: expect}\n  - {name: b, module: expect, enabled: false}")
    report = _engine(factory=fail).run(config)
    assert _statuses(report) == {"a": "error", "b": "skipped"}
    assert report.results[0].message == "DuckDB database file not found: x.duckdb"
    assert report.exit_code == EXIT_CHECKS_FAILED

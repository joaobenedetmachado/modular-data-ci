from collections.abc import Sequence
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from modular_data_ci.config import WhenConfig, evaluate_when, parse_config
from modular_data_ci.connections import ColumnInfo
from modular_data_ci.errors import ConfigError
from modular_data_ci.results import CheckStatus


class ScalarSource:
    def __init__(self, value: Any) -> None:
        self.value = value
        self.calls = 0

    def query(self, sql: str, parameters: Sequence[Any] | None = None) -> list[tuple[Any, ...]]:
        return [(self.value,)]

    def scalar(self, sql: str, parameters: Sequence[Any] | None = None) -> Any:
        self.calls += 1
        return self.value

    def columns(self, table: str) -> list[ColumnInfo]:
        return []

    def close(self) -> None:
        pass


def _when(**data: Any) -> WhenConfig:
    return WhenConfig.model_validate(data)


def _evaluate(when, env=None, statuses=None, source=None):
    return evaluate_when(when, env=env or {}, statuses=statuses or {}, source=source)


# --- model ------------------------------------------------------------------


def test_when_needs_at_least_one_condition():
    with pytest.raises(ValidationError, match="at least one"):
        WhenConfig()


def test_env_values_are_normalized_to_string_tuples():
    when = _when(env={"CI": True, "TARGET": "prod", "BRANCH": ["main", "release"], "N": 1})
    assert when.env == {
        "CI": ("true",),
        "TARGET": ("prod",),
        "BRANCH": ("main", "release"),
        "N": ("1",),
    }


@pytest.mark.parametrize("env", [{"BAD-NAME": "x"}, {"X": []}, {"X": {"a": 1}}])
def test_invalid_env_conditions(env):
    with pytest.raises(ValidationError):
        _when(env=env)


def test_single_dependency_string_is_accepted():
    assert _when(depends_on="a").depends_on == ("a",)


def test_unknown_when_key_is_rejected():
    with pytest.raises(ValidationError):
        _when(if_env={"A": "1"})


# --- evaluation -------------------------------------------------------------


def test_no_when_always_runs():
    assert _evaluate(None).run


def test_env_match_and_mismatch():
    when = _when(env={"BRANCH": ["main", "release"]})
    assert _evaluate(when, env={"BRANCH": "release"}).run
    decision = _evaluate(when, env={"BRANCH": "dev"})
    assert not decision.run
    assert decision.reason == "env BRANCH='dev', expected 'main' or 'release'"
    assert _evaluate(when).reason == "env BRANCH is not set"


@pytest.mark.parametrize(
    ("statuses", "run", "reason"),
    [
        ({"a": CheckStatus.SUCCESS}, True, ""),
        ({"a": CheckStatus.FAILURE}, False, "dependency 'a' ended with failure"),
        ({"a": CheckStatus.SKIPPED}, False, "dependency 'a' ended with skipped"),
        ({}, False, "dependency 'a' was not run"),
    ],
)
def test_depends_on(statuses, run, reason):
    decision = _evaluate(_when(depends_on=["a"]), statuses=statuses)
    assert (decision.run, decision.reason) == (run, reason)


@pytest.mark.parametrize(
    ("value", "run"),
    [(True, True), (False, False), (1, True), (0, False), (Decimal("0.5"), True), (None, False)],
)
def test_sql_predicate(value, run):
    assert _evaluate(_when(sql="SELECT 1"), source=ScalarSource(value)).run is run


def test_sql_predicate_rejects_non_boolean_results():
    with pytest.raises(ValueError, match="boolean or number"):
        _evaluate(_when(sql="SELECT 'yes'"), source=ScalarSource("yes"))


def test_cheap_conditions_short_circuit_sql():
    source = ScalarSource(True)
    when = _when(env={"TARGET": "prod"}, sql="SELECT 1")
    assert not _evaluate(when, env={"TARGET": "dev"}, source=source).run
    assert source.calls == 0


def test_all_conditions_must_hold():
    when = _when(env={"TARGET": "prod"}, depends_on="a", sql="SELECT 1")
    decision = _evaluate(
        when,
        env={"TARGET": "prod"},
        statuses={"a": CheckStatus.SUCCESS},
        source=ScalarSource(True),
    )
    assert decision.run


# --- dependencies in a full config ------------------------------------------


def _config_with(checks: str):
    return parse_config(f"connection: {{type: duckdb}}\nchecks:\n{checks}", env={})


def test_dependency_on_earlier_check_is_valid():
    config = _config_with(
        "  - {name: a, module: schema}\n  - {name: b, module: freshness, when: {depends_on: a}}"
    )
    assert config.get_check("b").when.depends_on == ("a",)


@pytest.mark.parametrize(
    ("checks", "message"),
    [
        ("  - {name: a, module: m, when: {depends_on: a}}", "cannot depend on itself"),
        ("  - {name: a, module: m, when: {depends_on: zz}}", "unknown check 'zz'"),
        (
            "  - {name: a, module: m, when: {depends_on: b}}\n  - {name: b, module: m}",
            "declared later; move 'b' above 'a'",
        ),
    ],
)
def test_invalid_dependencies(checks, message):
    with pytest.raises(ConfigError, match=message):
        _config_with(checks)

import pytest

from modular_data_ci.config import parse_config, plan_checks
from modular_data_ci.errors import ConfigError, SelectionError

CONFIG = """
connection: {type: duckdb}
modules:
  aggregation: {enabled: false}
checks:
  - {name: s1, module: schema}
  - {name: f1, module: freshness, enabled: false}
  - {name: a1, module: aggregation}
  - {name: c1, module: custom_sql}
"""


@pytest.fixture
def config():
    return parse_config(CONFIG, env={})


def _summary(planned):
    return [(p.check.name, p.skip_reason) for p in planned]


def test_default_plan_keeps_order_and_marks_disabled(config):
    assert _summary(plan_checks(config)) == [
        ("s1", None),
        ("f1", "disabled in config"),
        ("a1", "module 'aggregation' is disabled in config"),
        ("c1", None),
    ]


def test_will_run(config):
    assert [p.check.name for p in plan_checks(config) if p.will_run] == ["s1", "c1"]


def test_only_filter(config):
    assert _summary(plan_checks(config, only=["c1", "s1"])) == [("s1", None), ("c1", None)]


def test_skip_filter(config):
    names = [p.check.name for p in plan_checks(config, skip=["s1", "a1"])]
    assert names == ["f1", "c1"]


def test_module_filter(config):
    assert [p.check.name for p in plan_checks(config, modules=["custom_sql"])] == ["c1"]


def test_filters_combine(config):
    planned = plan_checks(config, modules=["schema", "custom_sql"], skip=["c1"])
    assert [p.check.name for p in planned] == ["s1"]


def test_selecting_a_disabled_check_still_reports_it_skipped(config):
    assert _summary(plan_checks(config, only=["f1"])) == [("f1", "disabled in config")]


def test_unknown_names_in_filters_are_errors(config):
    with pytest.raises(SelectionError, match=r"unknown check\(s\): nope"):
        plan_checks(config, only=["nope"])
    with pytest.raises(SelectionError, match="no check uses module"):
        plan_checks(config, modules=["schemaa"])


def test_unused_module_settings_are_rejected():
    text = CONFIG.replace("aggregation: {enabled: false}", "agregation: {enabled: false}")
    with pytest.raises(ConfigError, match="'modules' lists agregation, but no check uses it"):
        parse_config(text, env={})

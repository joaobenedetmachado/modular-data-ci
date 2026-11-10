from pathlib import Path

import pytest

from modular_data_ci.config import load_config, parse_config
from modular_data_ci.config.loader import interpolate_env
from modular_data_ci.errors import ConfigError

VALID = """
connection: {type: duckdb, path: data.duckdb}
checks:
  - name: orders_fresh
    module: freshness
    table: orders
"""


def _problems(text: str, env: dict[str, str] | None = None) -> list[str]:
    with pytest.raises(ConfigError) as exc:
        parse_config(text, env=env or {}, source="test.yml")
    return exc.value.problems


# --- files ------------------------------------------------------------------


def test_load_config_from_file(tmp_path: Path):
    path = tmp_path / "modular-data-ci.yml"
    path.write_text(VALID, encoding="utf-8")
    config = load_config(path, env={})
    assert config.checks[0].name == "orders_fresh"


def test_missing_file(tmp_path: Path):
    with pytest.raises(ConfigError, match="file not found"):
        load_config(tmp_path / "nope.yml")


def test_directory_instead_of_file(tmp_path: Path):
    with pytest.raises(ConfigError, match="directory"):
        load_config(tmp_path)


# --- YAML -------------------------------------------------------------------


def test_yaml_syntax_error_reports_line():
    (problem,) = _problems("connection: {type: duckdb\nchecks: [")
    assert problem.startswith("YAML syntax error at line")


def test_duplicate_keys_are_rejected():
    text = VALID + "    table: other\n"
    (problem,) = _problems(text)
    assert "duplicate key 'table'" in problem
    assert "line 7" in problem


@pytest.mark.parametrize(("text", "message"), [("", "empty"), ("- a\n- b", "mapping")])
def test_empty_or_non_mapping_file(text, message):
    (problem,) = _problems(text)
    assert message in problem


# --- environment variables --------------------------------------------------


def test_env_interpolation_with_and_without_default():
    data = {"a": "${HOST}:${PORT:-5432}", "b": ["${MISSING:-x}"], "c": 3}
    result = interpolate_env(data, {"HOST": "db"})
    assert result == {"a": "db:5432", "b": ["x"], "c": 3}


def test_default_applies_to_empty_value():
    assert interpolate_env("${EMPTY:-fallback}", {"EMPTY": ""}) == "fallback"


def test_escaped_reference_is_kept_literally():
    assert interpolate_env("cost: $${PRICE}", {"PRICE": "1"}) == "cost: ${PRICE}"


def test_postgres_style_placeholders_are_untouched():
    assert interpolate_env("WHERE a = $1 AND b = $$x$$", {}) == "WHERE a = $1 AND b = $$x$$"


def test_missing_variables_are_all_reported_with_paths():
    with pytest.raises(ConfigError) as exc:
        interpolate_env({"connection": {"url": "${DB_URL}"}, "x": ["${OTHER}"]}, {})
    problems = exc.value.problems
    assert len(problems) == 2
    assert problems[0].startswith("connection.url: environment variable DB_URL is not set")
    assert problems[1].startswith("x[0]: environment variable OTHER is not set")


def test_invalid_variable_reference():
    with pytest.raises(ConfigError, match="invalid variable reference"):
        interpolate_env("${1BAD}", {})


def test_env_can_disable_a_check_or_module():
    text = """
connection: {type: duckdb}
modules:
  freshness: {enabled: "${RUN_FRESHNESS:-true}"}
checks:
  - {name: a, module: freshness, enabled: "${RUN_A:-true}"}
"""
    config = parse_config(text, env={"RUN_A": "false", "RUN_FRESHNESS": "false"})
    assert config.checks[0].enabled is False
    assert config.module_enabled("freshness") is False
    defaults = parse_config(text, env={})
    assert defaults.checks[0].enabled is True
    assert defaults.module_enabled("freshness") is True


def test_env_used_in_connection():
    text = """
connection: {type: sqlalchemy, url: "${DB_URL}"}
checks: [{name: a, module: custom_sql}]
"""
    config = parse_config(text, env={"DB_URL": "postgresql://u:p@h/db"})
    assert config.connection.url == "postgresql://u:p@h/db"


# --- validation messages ----------------------------------------------------


def test_errors_name_the_check_and_field():
    text = """
connection: {type: duckdb}
checks:
  - {name: ok, module: schema}
  - {name: bad, module: freshness, enabled: maybe}
"""
    (problem,) = _problems(text)
    assert problem.startswith("checks[1] (bad).enabled:")


def test_multiple_problems_are_all_reported():
    text = """
connection: {type: duckdb, pth: x}
checks:
  - {module: schema}
"""
    problems = _problems(text)
    assert "connection.pth: unknown key" in problems
    assert "checks[0].name: required field is missing" in problems


def test_unknown_connection_type_message():
    (problem,) = _problems("connection: {type: oracle}\nchecks: [{name: a, module: m}]")
    assert problem.startswith("connection: unknown type 'oracle'")


def test_config_error_message_lists_problems():
    with pytest.raises(ConfigError) as exc:
        parse_config("connection: {type: duckdb, pth: x}\nchecks: []", env={}, source="f.yml")
    text = str(exc.value)
    assert text.startswith("Invalid configuration in f.yml (2 problems):")
    assert "  - connection.pth: unknown key" in text

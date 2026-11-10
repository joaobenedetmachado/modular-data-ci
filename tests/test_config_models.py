from datetime import timedelta

import pytest
from pydantic import ValidationError

from modular_data_ci.config import (
    CheckConfig,
    Config,
    DuckDBConnection,
    SQLAlchemyConnection,
    parse_duration,
)


def _config(**overrides):
    data = {
        "connection": {"type": "duckdb", "path": "data.duckdb"},
        "checks": [{"name": "orders_fresh", "module": "freshness", "table": "orders"}],
    }
    data.update(overrides)
    return Config.model_validate(data)


def test_minimal_config_is_valid_with_defaults():
    config = _config()
    assert config.version == 1
    assert isinstance(config.connection, DuckDBConnection)
    check = config.checks[0]
    assert check.enabled is True
    assert check.required is True


def test_module_specific_keys_are_exposed_as_params():
    check = _config().checks[0]
    assert check.params == {"table": "orders"}


def test_common_keys_are_not_in_params():
    check = CheckConfig.model_validate(
        {"name": "c", "module": "m", "enabled": False, "required": False, "description": "d"}
    )
    assert check.params == {}


def test_sqlalchemy_connection_is_selected_by_type():
    config = _config(connection={"type": "sqlalchemy", "url": "postgresql://localhost/db"})
    assert isinstance(config.connection, SQLAlchemyConnection)


def test_unknown_connection_type_is_rejected():
    with pytest.raises(ValidationError):
        _config(connection={"type": "oracle"})


def test_unknown_top_level_key_is_rejected():
    with pytest.raises(ValidationError, match="extra"):
        _config(chekcs=[])


def test_unsupported_version_is_rejected():
    with pytest.raises(ValidationError):
        _config(version=2)


def test_at_least_one_check_is_required():
    with pytest.raises(ValidationError):
        _config(checks=[])


def test_duplicate_check_names_are_rejected():
    checks = [
        {"name": "dup", "module": "freshness"},
        {"name": "dup", "module": "schema"},
        {"name": "ok", "module": "schema"},
    ]
    with pytest.raises(ValidationError, match="duplicated: dup"):
        _config(checks=checks)


@pytest.mark.parametrize("name", ["", "has space", "-leading-dash", "x" * 129])
def test_invalid_check_names_are_rejected(name):
    with pytest.raises(ValidationError):
        CheckConfig(name=name, module="m")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("90s", timedelta(seconds=90)),
        ("30m", timedelta(minutes=30)),
        ("24h", timedelta(hours=24)),
        ("1.5d", timedelta(hours=36)),
        ("2w", timedelta(weeks=2)),
        (3600, timedelta(hours=1)),
    ],
)
def test_parse_duration(raw, expected):
    assert parse_duration(raw) == expected


@pytest.mark.parametrize("raw", ["24", "1y", "h", "", True, None])
def test_parse_duration_rejects_invalid_values(raw):
    with pytest.raises(ValueError, match="duration"):
        parse_duration(raw)

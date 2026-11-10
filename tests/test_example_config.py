"""The shipped example must stay valid, including every module's params."""

from pathlib import Path

import pytest

from modular_data_ci.config import load_config, plan_checks
from modular_data_ci.modules.aggregation import AggregationParams
from modular_data_ci.modules.custom_sql import CustomSqlParams
from modular_data_ci.modules.freshness import FreshnessParams
from modular_data_ci.modules.schema import SchemaParams

EXAMPLE = Path(__file__).parent.parent / "examples" / "modular-data-ci.yml"
PARAMS = {
    "schema": SchemaParams,
    "freshness": FreshnessParams,
    "aggregation": AggregationParams,
    "custom_sql": CustomSqlParams,
}


@pytest.fixture
def config():
    return load_config(EXAMPLE, env={})


def test_example_loads_with_defaults(config):
    assert config.connection.path == "examples/data/shop.duckdb"
    assert config.module_enabled("aggregation")


@pytest.mark.parametrize("index", range(7))
def test_example_check_params_are_valid(config, index):
    check = config.checks[index]
    PARAMS[check.module].model_validate(check.params)


def test_example_env_overrides(config):
    overridden = load_config(
        EXAMPLE, env={"MDCI_DUCKDB_PATH": "/tmp/x.duckdb", "MDCI_RUN_AGGREGATIONS": "false"}
    )
    assert overridden.connection.path == "/tmp/x.duckdb"
    skipped = [p.check.name for p in plan_checks(overridden) if not p.will_run]
    assert skipped == ["revenue_matches_target", "daily_orders_stable", "legacy_table_schema"]


def test_example_check_count_matches_parametrization(config):
    assert len(config.checks) == 7

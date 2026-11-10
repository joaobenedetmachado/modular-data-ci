from datetime import timedelta

import pytest
from pydantic import ValidationError

from modular_data_ci.modules.aggregation import AggregationParams
from modular_data_ci.modules.custom_sql import CustomSqlParams
from modular_data_ci.modules.freshness import FreshnessParams
from modular_data_ci.modules.schema import SchemaParams


def test_schema_params_with_column_specs():
    params = SchemaParams.model_validate(
        {
            "table": "orders",
            "columns": {"order_id": {"type": "integer", "nullable": False}, "note": {}},
            "allow_extra_columns": False,
        }
    )
    assert params.columns["order_id"].nullable is False
    assert params.columns["note"].type is None
    assert params.columns["note"].required is True


def test_schema_params_reject_typos():
    with pytest.raises(ValidationError, match="extra"):
        SchemaParams.model_validate({"table": "t", "columns": {"a": {"nulable": False}}})


def test_schema_params_need_columns():
    with pytest.raises(ValidationError):
        SchemaParams.model_validate({"table": "t", "columns": {}})


def test_freshness_params_parse_duration():
    params = FreshnessParams.model_validate(
        {"table": "orders", "timestamp_column": "created_at", "max_age": "24h"}
    )
    assert params.max_age == timedelta(hours=24)


def test_freshness_rejects_non_positive_age():
    with pytest.raises(ValidationError, match="greater than zero"):
        FreshnessParams.model_validate({"table": "t", "timestamp_column": "c", "max_age": 0})


def test_custom_sql_accepts_shorthand_condition():
    params = CustomSqlParams.model_validate({"sql": "SELECT 1", "condition": "> 0"})
    assert params.condition.evaluate(1)


def test_aggregation_with_expected_value():
    params = AggregationParams.model_validate(
        {
            "table": "orders",
            "function": "sum",
            "column": "amount",
            "condition": {"operator": "==", "value": 1000, "tolerance": {"relative": 0.05}},
        }
    )
    assert params.condition is not None
    assert params.condition.evaluate(1030)


def test_aggregation_compare_to_previous_period():
    params = AggregationParams.model_validate(
        {
            "table": "orders",
            "function": "count",
            "period": {"column": "created_at", "window": "1d"},
            "compare_to_previous": {"max_relative_change": 0.2},
        }
    )
    assert params.period is not None
    assert params.period.window == timedelta(days=1)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"function": "sum"}, "'column' is required"),
        ({"condition": None}, "exactly one"),
        ({"compare_to_previous": {"max_relative_change": 0.1}}, "exactly one"),
        (
            {"condition": None, "compare_to_previous": {"max_relative_change": 0.1}},
            "requires 'period'",
        ),
        ({"function": "median"}, "function"),
    ],
)
def test_aggregation_invalid_combinations(overrides, message):
    data = {"table": "t", "function": "count", "condition": "> 0"}
    data.update(overrides)
    data = {k: v for k, v in data.items() if v is not None}
    with pytest.raises(ValidationError, match=message):
        AggregationParams.model_validate(data)

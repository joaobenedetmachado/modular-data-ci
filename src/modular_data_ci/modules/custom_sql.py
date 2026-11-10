"""Custom SQL module: a query returns one number that must meet a condition."""

from __future__ import annotations

from pydantic import Field

from modular_data_ci.conditions import Condition
from modular_data_ci.modules._sql import format_number, to_number
from modular_data_ci.modules.base import ExecutionContext, ModuleParams, ValidationModule
from modular_data_ci.results import CheckOutcome


class CustomSqlParams(ModuleParams):
    sql: str = Field(min_length=1)
    """A query returning exactly one row with one numeric (or boolean) column."""
    condition: Condition


class CustomSqlModule(ValidationModule[CustomSqlParams]):
    name = "custom_sql"
    params_model = CustomSqlParams

    def run(self, params: CustomSqlParams, context: ExecutionContext) -> CheckOutcome:
        rows = context.source.query(params.sql)
        expected = params.condition.describe()
        if not rows:
            return CheckOutcome.failure(f"query returned no rows, expected a value {expected}")
        if len(rows) > 1 or len(rows[0]) != 1:
            return CheckOutcome.error(
                "query must return exactly one row with one column, got "
                f"{len(rows)} row(s) and {len(rows[0])} column(s)"
            )
        try:
            value = to_number(rows[0][0])
        except TypeError as exc:
            return CheckOutcome.error(f"query result is not numeric: {exc}")
        if value is None:
            return CheckOutcome.failure(f"query returned NULL, expected a value {expected}")

        details = {"value": value, "condition": expected}
        if params.condition.evaluate(value):
            return CheckOutcome.success(f"value {format_number(value)} {expected}", **details)
        return CheckOutcome.failure(f"value {format_number(value)}, expected {expected}", **details)

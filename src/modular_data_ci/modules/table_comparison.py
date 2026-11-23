"""Table comparison module: an aggregate matches between two tables.

Typical use: a staging table and its production copy, or a source table and the
model built from it, must have the same row count or the same total.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from modular_data_ci.conditions import Tolerance
from modular_data_ci.connections.base import DataSource
from modular_data_ci.modules._sql import format_number, to_number, where_clause
from modular_data_ci.modules.base import ExecutionContext, ModuleParams, ValidationModule
from modular_data_ci.results import CheckOutcome


class Side(ModuleParams):
    table: str = Field(min_length=1)
    where: str | None = None


class TableComparisonParams(ModuleParams):
    source: Side
    target: Side
    function: Literal["count", "count_distinct", "sum", "min", "max"] = "count"
    column: str | None = None
    tolerance: Tolerance | None = None
    """Allowed difference, relative to the source value."""

    @model_validator(mode="after")
    def _column(self) -> TableComparisonParams:
        if self.function != "count" and self.column is None:
            raise ValueError(f"'column' is required for function '{self.function}'")
        return self


def _aggregate(source: DataSource, params: TableComparisonParams, side: Side) -> float:
    if params.function == "count":
        expression = "COUNT(*)"
    elif params.function == "count_distinct":
        expression = f"COUNT(DISTINCT {source.quote(params.column or '')})"
    else:
        expression = f"{params.function.upper()}({source.quote(params.column or '')})"
    sql = f"SELECT {expression} FROM {source.quote(side.table)}{where_clause(side.where)}"
    return to_number(source.scalar(sql)) or 0.0


class TableComparisonModule(ValidationModule[TableComparisonParams]):
    name = "table_comparison"
    params_model = TableComparisonParams

    def run(self, params: TableComparisonParams, context: ExecutionContext) -> CheckOutcome:
        expected = _aggregate(context.source, params, params.source)
        actual = _aggregate(context.source, params, params.target)
        difference = actual - expected
        allowed = params.tolerance.allowance(expected) if params.tolerance else 0.0
        label = params.function if params.column is None else f"{params.function}({params.column})"
        details = {
            "function": label,
            "source": params.source.table,
            "target": params.target.table,
            "source_value": expected,
            "target_value": actual,
            "difference": difference,
            "allowed_difference": allowed,
        }
        summary = (
            f"{label}: {params.source.table}={format_number(expected)}, "
            f"{params.target.table}={format_number(actual)}"
        )
        if abs(difference) <= allowed:
            return CheckOutcome.success(summary, **details)
        return CheckOutcome.failure(
            f"{summary} (difference {format_number(difference)}, "
            f"allowed ±{format_number(allowed)})",
            **details,
        )

"""Value range module: every value of a column lies between ``min`` and ``max``."""

from __future__ import annotations

from pydantic import Field, model_validator

from modular_data_ci.modules._sql import format_number, to_number, where_clause
from modular_data_ci.modules.base import ExecutionContext, ModuleParams, ValidationModule
from modular_data_ci.results import CheckOutcome


class ValueRangeParams(ModuleParams):
    table: str = Field(min_length=1)
    column: str = Field(min_length=1)
    min: float | None = None
    max: float | None = None
    inclusive: bool = True
    """When False, values equal to ``min`` or ``max`` are out of range."""
    where: str | None = None

    @model_validator(mode="after")
    def _bounds(self) -> ValueRangeParams:
        if self.min is None and self.max is None:
            raise ValueError("set 'min' and/or 'max'")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("'min' must not be greater than 'max'")
        return self


class ValueRangeModule(ValidationModule[ValueRangeParams]):
    name = "value_range"
    params_model = ValueRangeParams

    def run(self, params: ValueRangeParams, context: ExecutionContext) -> CheckOutcome:
        source = context.source
        column = source.quote(params.column)
        low, high = ("<", ">") if params.inclusive else ("<=", ">=")
        outside = []
        bind = {}
        if params.min is not None:
            outside.append(f"{column} {low} {source.placeholder('low')}")
            bind["low"] = params.min
        if params.max is not None:
            outside.append(f"{column} {high} {source.placeholder('high')}")
            bind["high"] = params.max
        table = source.quote(params.table)
        sql = (
            f"SELECT COUNT(*), MIN({column}), MAX({column}) FROM {table}"
            f"{where_clause(params.where, ' OR '.join(outside))}"
        )
        count, smallest, largest = source.query(sql, bind)[0]
        details = {
            "table": params.table,
            "column": params.column,
            "out_of_range": int(count or 0),
            "min": params.min,
            "max": params.max,
        }
        bounds = _describe(params)
        if not count:
            return CheckOutcome.success(f"all {params.column} values {bounds}", **details)
        observed = f"{format_number(to_number(smallest))}..{format_number(to_number(largest))}"
        details["out_of_range_span"] = observed
        return CheckOutcome.failure(
            f"{count} row(s) with {params.column} outside {bounds} (found {observed})", **details
        )


def _describe(params: ValueRangeParams) -> str:
    left = "[" if params.inclusive else "("
    right = "]" if params.inclusive else ")"
    low = "-inf" if params.min is None else format_number(params.min)
    high = "inf" if params.max is None else format_number(params.max)
    return f"in {left}{low}, {high}{right}"

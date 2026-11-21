"""Accepted values module: a column only contains values from an allowed list."""

from __future__ import annotations

from typing import Union

from pydantic import Field

from modular_data_ci.modules._sql import where_clause
from modular_data_ci.modules.base import ExecutionContext, ModuleParams, ValidationModule
from modular_data_ci.results import CheckOutcome

Value = Union[str, int, float, bool]  # noqa: UP007 - pydantic needs a runtime union on 3.10


class AcceptedValuesParams(ModuleParams):
    table: str = Field(min_length=1)
    column: str = Field(min_length=1)
    values: list[Value] = Field(min_length=1)
    allow_null: bool = True
    where: str | None = None
    sample_size: int = Field(default=10, ge=0, le=100)


class AcceptedValuesModule(ValidationModule[AcceptedValuesParams]):
    name = "accepted_values"
    params_model = AcceptedValuesParams

    def run(self, params: AcceptedValuesParams, context: ExecutionContext) -> CheckOutcome:
        source = context.source
        column = source.quote(params.column)
        bind = {f"v{i}": value for i, value in enumerate(params.values)}
        allowed = ", ".join(source.placeholder(name) for name in bind)
        outside = f"{column} NOT IN ({allowed})"
        if not params.allow_null:
            outside = f"({outside} OR {column} IS NULL)"
        else:
            outside = f"({column} IS NOT NULL AND {outside})"
        base = f"FROM {source.quote(params.table)}{where_clause(params.where, outside)}"
        invalid = int(source.scalar(f"SELECT COUNT(*) {base}", bind) or 0)
        details: dict[str, object] = {
            "table": params.table,
            "column": params.column,
            "invalid_rows": invalid,
        }
        if not invalid:
            return CheckOutcome.success(f"all {params.column} values accepted", **details)
        if params.sample_size:
            rows = source.query(
                f"SELECT {column}, COUNT(*) {base} GROUP BY {column} "
                f"ORDER BY COUNT(*) DESC LIMIT {params.sample_size}",
                bind,
            )
            details["unexpected_values"] = {str(value): count for value, count in rows}
        shown = ", ".join(map(str, details.get("unexpected_values", {})))
        suffix = f": {shown}" if shown else ""
        return CheckOutcome.failure(
            f"{invalid} row(s) with unexpected {params.column}{suffix}", **details
        )

"""Not-null module: the listed columns contain no NULL values."""

from __future__ import annotations

from pydantic import Field

from modular_data_ci.modules._sql import where_clause
from modular_data_ci.modules.base import ExecutionContext, ModuleParams, ValidationModule
from modular_data_ci.results import CheckOutcome


class NotNullParams(ModuleParams):
    table: str = Field(min_length=1)
    columns: list[str] = Field(min_length=1)
    where: str | None = None
    max_nulls: int = Field(default=0, ge=0)
    """NULLs allowed per column before the check fails."""


class NotNullModule(ValidationModule[NotNullParams]):
    name = "not_null"
    params_model = NotNullParams

    def run(self, params: NotNullParams, context: ExecutionContext) -> CheckOutcome:
        source = context.source
        counts = ", ".join(f"COUNT(*) - COUNT({source.quote(column)})" for column in params.columns)
        sql = f"SELECT {counts} FROM {source.quote(params.table)}{where_clause(params.where)}"
        row = source.query(sql)[0]
        nulls = {column: int(value or 0) for column, value in zip(params.columns, row, strict=True)}
        offending = {column: n for column, n in nulls.items() if n > params.max_nulls}
        details = {"table": params.table, "null_counts": nulls}
        if offending:
            listed = ", ".join(f"{column} ({n})" for column, n in offending.items())
            return CheckOutcome.failure(f"NULL values in {listed}", **details)
        return CheckOutcome.success(
            f"no NULLs in {len(params.columns)} column(s)"
            if params.max_nulls == 0
            else f"at most {params.max_nulls} NULLs per column",
            **details,
        )

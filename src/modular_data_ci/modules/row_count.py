"""Row count module: the number of rows is within ``min`` and/or ``max``."""

from __future__ import annotations

from pydantic import Field, model_validator

from modular_data_ci.modules._sql import where_clause
from modular_data_ci.modules.base import ExecutionContext, ModuleParams, ValidationModule
from modular_data_ci.results import CheckOutcome


class RowCountParams(ModuleParams):
    table: str = Field(min_length=1)
    min: int | None = Field(default=None, ge=0)
    max: int | None = Field(default=None, ge=0)
    where: str | None = None

    @model_validator(mode="after")
    def _bounds(self) -> RowCountParams:
        if self.min is None and self.max is None:
            raise ValueError("set 'min' and/or 'max'")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("'min' must not be greater than 'max'")
        return self


class RowCountModule(ValidationModule[RowCountParams]):
    name = "row_count"
    params_model = RowCountParams

    def run(self, params: RowCountParams, context: ExecutionContext) -> CheckOutcome:
        source = context.source
        sql = f"SELECT COUNT(*) FROM {source.quote(params.table)}{where_clause(params.where)}"
        count = int(source.scalar(sql) or 0)
        details = {"table": params.table, "row_count": count, "min": params.min, "max": params.max}
        if params.min is not None and count < params.min:
            return CheckOutcome.failure(f"{count} rows, expected at least {params.min}", **details)
        if params.max is not None and count > params.max:
            return CheckOutcome.failure(f"{count} rows, expected at most {params.max}", **details)
        return CheckOutcome.success(f"{count} rows", **details)

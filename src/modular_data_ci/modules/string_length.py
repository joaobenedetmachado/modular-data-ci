"""String length module: text values are between ``min_length`` and ``max_length``."""

from __future__ import annotations

from pydantic import Field, model_validator

from modular_data_ci.modules._sql import where_clause
from modular_data_ci.modules.base import ExecutionContext, ModuleParams, ValidationModule
from modular_data_ci.results import CheckOutcome


class StringLengthParams(ModuleParams):
    table: str = Field(min_length=1)
    column: str = Field(min_length=1)
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=0)
    where: str | None = None

    @model_validator(mode="after")
    def _bounds(self) -> StringLengthParams:
        if self.min_length is None and self.max_length is None:
            raise ValueError("set 'min_length' and/or 'max_length'")
        if (
            self.min_length is not None
            and self.max_length is not None
            and self.min_length > self.max_length
        ):
            raise ValueError("'min_length' must not be greater than 'max_length'")
        return self


class StringLengthModule(ValidationModule[StringLengthParams]):
    name = "string_length"
    params_model = StringLengthParams

    def run(self, params: StringLengthParams, context: ExecutionContext) -> CheckOutcome:
        source = context.source
        length = f"LENGTH({source.quote(params.column)})"
        outside = []
        if params.min_length is not None:
            outside.append(f"{length} < {int(params.min_length)}")
        if params.max_length is not None:
            outside.append(f"{length} > {int(params.max_length)}")
        sql = (
            f"SELECT COUNT(*), MIN({length}), MAX({length}) FROM {source.quote(params.table)}"
            f"{where_clause(params.where, ' OR '.join(outside))}"
        )
        count, shortest, longest = source.query(sql)[0]
        details = {
            "table": params.table,
            "column": params.column,
            "invalid_rows": int(count or 0),
            "min_length": params.min_length,
            "max_length": params.max_length,
        }
        if not count:
            return CheckOutcome.success(f"all {params.column} lengths within bounds", **details)
        return CheckOutcome.failure(
            f"{count} row(s) with {params.column} length outside bounds "
            f"(found lengths {shortest}..{longest})",
            **details,
        )

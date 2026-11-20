"""Uniqueness module: no two rows share the same value(s) in the key columns."""

from __future__ import annotations

from pydantic import Field, field_validator

from modular_data_ci.modules._sql import where_clause
from modular_data_ci.modules.base import ExecutionContext, ModuleParams, ValidationModule
from modular_data_ci.results import CheckOutcome


class UniquenessParams(ModuleParams):
    table: str = Field(min_length=1)
    columns: list[str] = Field(min_length=1)
    """One column, or several forming a composite key."""
    where: str | None = None
    ignore_nulls: bool = True
    """Rows with a NULL in any key column are not compared (SQL semantics)."""
    sample_size: int = Field(default=5, ge=0, le=100)
    """How many duplicated keys to include in the result details."""

    @field_validator("columns", mode="before")
    @classmethod
    def _single(cls, value: object) -> object:
        return [value] if isinstance(value, str) else value


class UniquenessModule(ValidationModule[UniquenessParams]):
    name = "uniqueness"
    params_model = UniquenessParams

    def run(self, params: UniquenessParams, context: ExecutionContext) -> CheckOutcome:
        source = context.source
        keys = ", ".join(source.quote(column) for column in params.columns)
        not_null = (
            " AND ".join(f"{source.quote(c)} IS NOT NULL" for c in params.columns)
            if params.ignore_nulls
            else None
        )
        grouped = (
            f"SELECT {keys}, COUNT(*) AS n FROM {source.quote(params.table)}"
            f"{where_clause(params.where, not_null)} GROUP BY {keys} HAVING COUNT(*) > 1"
        )
        summary = source.query(f"SELECT COUNT(*), COALESCE(SUM(n), 0) FROM ({grouped}) d")[0]
        duplicate_keys, duplicate_rows = int(summary[0] or 0), int(summary[1] or 0)
        details = {
            "table": params.table,
            "columns": params.columns,
            "duplicate_keys": duplicate_keys,
            "duplicate_rows": duplicate_rows,
        }
        label = ", ".join(params.columns)
        if not duplicate_keys:
            return CheckOutcome.success(f"({label}) is unique", **details)
        if params.sample_size:
            rows = source.query(f"{grouped} ORDER BY n DESC LIMIT {params.sample_size}")
            details["sample"] = [
                {**dict(zip(params.columns, row[:-1], strict=True)), "count": row[-1]}
                for row in rows
            ]
        return CheckOutcome.failure(
            f"{duplicate_keys} duplicated value(s) of ({label}) across {duplicate_rows} rows",
            **details,
        )

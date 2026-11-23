"""Failing rows module: a query selects the rows that break a rule; zero rows passes.

This is the most flexible check: write the rule as SQL, return the offending rows,
and the first ``sample_size`` of them are included in the report.
"""

from __future__ import annotations

from pydantic import Field

from modular_data_ci.modules.base import ExecutionContext, ModuleParams, ValidationModule
from modular_data_ci.results import CheckOutcome


class FailingRowsParams(ModuleParams):
    sql: str = Field(min_length=1)
    """A SELECT returning the rows that violate the rule."""
    max_rows: int = Field(default=0, ge=0)
    """Rows tolerated before the check fails."""
    sample_size: int = Field(default=5, ge=0, le=100)


class FailingRowsModule(ValidationModule[FailingRowsParams]):
    name = "failing_rows"
    params_model = FailingRowsParams

    def run(self, params: FailingRowsParams, context: ExecutionContext) -> CheckOutcome:
        source = context.source
        query = params.sql.strip().rstrip(";")
        count = int(source.scalar(f"SELECT COUNT(*) FROM ({query}) failing_rows") or 0)
        details: dict[str, object] = {"failing_rows": count, "max_rows": params.max_rows}
        if count <= params.max_rows:
            message = "no failing rows" if count == 0 else f"{count} failing row(s), within limit"
            return CheckOutcome.success(message, **details)
        if params.sample_size:
            rows = source.query(f"SELECT * FROM ({query}) failing_rows LIMIT {params.sample_size}")
            details["sample"] = [list(row) for row in rows]
        return CheckOutcome.failure(
            f"{count} failing row(s), expected at most {params.max_rows}", **details
        )

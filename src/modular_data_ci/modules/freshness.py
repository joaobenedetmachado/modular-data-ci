"""Freshness module: the newest row is not older than ``max_age``."""

from __future__ import annotations

from pydantic import Field

from modular_data_ci.config.types import Duration
from modular_data_ci.modules._sql import format_duration, to_utc_datetime, where_clause
from modular_data_ci.modules.base import ExecutionContext, ModuleParams, ValidationModule
from modular_data_ci.results import CheckOutcome


class FreshnessParams(ModuleParams):
    table: str = Field(min_length=1)
    timestamp_column: str = Field(min_length=1)
    max_age: Duration
    """Maximum allowed age of the newest row, e.g. ``24h``."""
    where: str | None = None
    """Optional SQL filter applied before taking the newest timestamp."""


class FreshnessModule(ValidationModule[FreshnessParams]):
    name = "freshness"
    params_model = FreshnessParams

    def run(self, params: FreshnessParams, context: ExecutionContext) -> CheckOutcome:
        source = context.source
        sql = (
            f"SELECT MAX({source.quote(params.timestamp_column)}) "
            f"FROM {source.quote(params.table)}{where_clause(params.where)}"
        )
        value = source.scalar(sql)
        details = {"table": params.table, "max_age_seconds": params.max_age.total_seconds()}
        if value is None:
            return CheckOutcome.failure(
                f"no rows with a {params.timestamp_column} value in {params.table}", **details
            )

        newest = to_utc_datetime(value)
        age = context.now - newest
        details.update(newest=newest.isoformat(), age_seconds=age.total_seconds())
        if age > params.max_age:
            return CheckOutcome.failure(
                f"newest row is {format_duration(age)} old, "
                f"expected at most {format_duration(params.max_age)}",
                **details,
            )
        return CheckOutcome.success(f"newest row is {format_duration(age)} old", **details)

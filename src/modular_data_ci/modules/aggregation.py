"""Aggregation module: compare an aggregate with an expected value or the previous period.

Two modes, exactly one must be configured:

* ``condition``: compare the aggregate with an expected value
  (operator, value, optional tolerance).
* ``compare_to_previous``: compare the aggregate for the current ``period``
  window with the window right before it, allowing a maximum relative change.

With ``period``, the current window is ``[now - window, now)`` and the previous
window is ``[now - 2*window, now - window)``. Timestamps are assumed to be UTC.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from modular_data_ci.conditions import Condition
from modular_data_ci.config.types import Duration
from modular_data_ci.connections.base import DataSource
from modular_data_ci.modules._sql import format_number, timestamp_param, to_number, where_clause
from modular_data_ci.modules.base import ExecutionContext, ModuleParams, ValidationModule
from modular_data_ci.results import CheckOutcome

AggregateFunction = Literal["count", "count_distinct", "sum", "avg", "min", "max"]


class Period(ModuleParams):
    column: str = Field(min_length=1)
    """Timestamp/date column that defines the window."""
    window: Duration
    """Window length ending at the run's reference time, e.g. ``1d`` or ``7d``."""


class PreviousPeriodComparison(ModuleParams):
    max_relative_change: float = Field(ge=0)
    """Allowed change versus the previous window, as a fraction (0.2 means ±20%)."""


class AggregationParams(ModuleParams):
    table: str = Field(min_length=1)
    function: AggregateFunction
    column: str | None = None
    """Required for every function except ``count``."""
    where: str | None = None
    period: Period | None = None
    condition: Condition | None = None
    compare_to_previous: PreviousPeriodComparison | None = None

    @model_validator(mode="after")
    def _check_consistency(self) -> AggregationParams:
        if self.function != "count" and self.column is None:
            raise ValueError(f"'column' is required for function '{self.function}'")
        if (self.condition is None) == (self.compare_to_previous is None):
            raise ValueError("set exactly one of 'condition' or 'compare_to_previous'")
        if self.compare_to_previous is not None and self.period is None:
            raise ValueError("'compare_to_previous' requires 'period'")
        return self

    @property
    def label(self) -> str:
        return f"{self.function}({self.column or '*'})"


class AggregationModule(ValidationModule[AggregationParams]):
    name = "aggregation"
    params_model = AggregationParams

    def run(self, params: AggregationParams, context: ExecutionContext) -> CheckOutcome:
        if params.compare_to_previous is not None:
            return self._compare_to_previous(params, context)
        return self._compare_to_condition(params, context)

    def _compare_to_condition(
        self, params: AggregationParams, context: ExecutionContext
    ) -> CheckOutcome:
        if params.condition is None:  # pragma: no cover - guaranteed by params validation
            raise ValueError("condition is required")
        window = None
        if params.period is not None:
            window = (context.now - params.period.window, context.now)
        value = _aggregate(context.source, params, window)
        expected = params.condition.describe()
        details = {"value": value, "condition": expected, **_window_details(window)}
        if value is None:
            return CheckOutcome.failure(
                f"{params.label} is NULL (no matching rows), expected {expected}", **details
            )
        if params.condition.evaluate(value):
            return CheckOutcome.success(
                f"{params.label} = {format_number(value)} {expected}", **details
            )
        return CheckOutcome.failure(
            f"{params.label} = {format_number(value)}, expected {expected}", **details
        )

    def _compare_to_previous(
        self, params: AggregationParams, context: ExecutionContext
    ) -> CheckOutcome:
        if params.period is None or params.compare_to_previous is None:  # pragma: no cover
            raise ValueError("compare_to_previous needs period")  # guaranteed by params validation
        window = params.period.window
        current_window = (context.now - window, context.now)
        previous_window = (context.now - 2 * window, context.now - window)
        current = _aggregate(context.source, params, current_window) or 0.0
        previous = _aggregate(context.source, params, previous_window) or 0.0
        allowed = params.compare_to_previous.max_relative_change
        details = {
            "current": current,
            "previous": previous,
            "max_relative_change": allowed,
            **_window_details(current_window),
        }

        if previous == 0:
            if current == 0:
                return CheckOutcome.success(
                    f"{params.label} is 0 in both periods", relative_change=0.0, **details
                )
            return CheckOutcome.failure(
                f"{params.label} went from 0 to {format_number(current)}; "
                "relative change is undefined",
                relative_change=None,
                **details,
            )

        change = (current - previous) / abs(previous)
        summary = (
            f"{params.label} {format_number(previous)} -> {format_number(current)} "
            f"({change:+.1%}, allowed ±{allowed:.1%})"
        )
        if abs(change) <= allowed:
            return CheckOutcome.success(summary, relative_change=change, **details)
        return CheckOutcome.failure(summary, relative_change=change, **details)


def _aggregate(
    source: DataSource,
    params: AggregationParams,
    window: tuple[datetime, datetime] | None,
) -> float | None:
    column = source.quote(params.column) if params.column else None
    if params.function == "count":
        expression = f"COUNT({column})" if column else "COUNT(*)"
    elif params.function == "count_distinct":
        expression = f"COUNT(DISTINCT {column})"
    else:
        expression = f"{params.function.upper()}({column})"

    conditions = [params.where]
    parameters = None
    if window is not None and params.period is not None:
        period_column = source.quote(params.period.column)
        conditions.append(
            f"{period_column} >= {source.placeholder('period_start')} "
            f"AND {period_column} < {source.placeholder('period_end')}"
        )
        parameters = {
            "period_start": timestamp_param(source, window[0]),
            "period_end": timestamp_param(source, window[1]),
        }
    sql = f"SELECT {expression} FROM {source.quote(params.table)}{where_clause(*conditions)}"
    return to_number(source.scalar(sql, parameters))


def _window_details(window: tuple[datetime, datetime] | None) -> dict[str, str]:
    if window is None:
        return {}
    return {"window_start": window[0].isoformat(), "window_end": window[1].isoformat()}

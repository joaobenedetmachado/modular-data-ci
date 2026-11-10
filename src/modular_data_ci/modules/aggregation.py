"""Aggregation module settings. The module implementation arrives on Day 4.

Two modes, exactly one must be configured:

* ``condition``: compare the aggregate with an expected value
  (operator, value, optional tolerance).
* ``compare_to_previous``: compare the aggregate for the current ``period``
  window with the window right before it, allowing a maximum relative change.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from modular_data_ci.conditions import Condition
from modular_data_ci.config.types import Duration
from modular_data_ci.modules.base import ModuleParams

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

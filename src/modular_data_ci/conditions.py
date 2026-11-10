"""Numeric conditions shared by modules (aggregation, custom SQL, ...).

A condition can be written as a mapping::

    condition:
      operator: "=="
      value: 1000
      tolerance: {relative: 0.05}

or as a shorthand string without tolerance: ``"> 0"``, ``"== 100"``, ``"<= 2.5"``.
"""

from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Operator = Literal["==", "!=", ">", ">=", "<", "<="]

_SHORTHAND = re.compile(r"^\s*(==|!=|>=|<=|>|<)\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*$")


class Tolerance(BaseModel):
    """Allowed slack around a condition value.

    ``absolute`` is in the same unit as the value. ``relative`` is a fraction of the
    expected value (0.05 means 5%). When both are set, the larger allowance wins.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    absolute: float | None = Field(default=None, ge=0)
    relative: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _at_least_one(self) -> Tolerance:
        if self.absolute is None and self.relative is None:
            raise ValueError("tolerance needs 'absolute' and/or 'relative'")
        return self

    def allowance(self, reference: float) -> float:
        return max(self.absolute or 0.0, (self.relative or 0.0) * abs(reference))


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operator: Operator
    value: float
    tolerance: Tolerance | None = None

    @model_validator(mode="before")
    @classmethod
    def _parse_shorthand(cls, data: Any) -> Any:
        if isinstance(data, str):
            match = _SHORTHAND.match(data)
            if match is None:
                raise ValueError(
                    f"invalid condition {data!r}; expected an operator and a number, "
                    "e.g. '> 0' or '== 100'"
                )
            return {"operator": match[1], "value": float(match[2])}
        return data

    @property
    def slack(self) -> float:
        return self.tolerance.allowance(self.value) if self.tolerance else 0.0

    def evaluate(self, actual: float | int | Decimal | None) -> bool:
        """Return True when ``actual`` satisfies the condition.

        ``None`` and NaN never satisfy a condition: a missing value is a failure,
        not a pass.
        """
        if actual is None or isinstance(actual, bool):
            return False
        number = float(actual)
        if math.isnan(number):
            return False

        slack = self.slack
        target = self.value
        if self.operator == "==":
            return abs(number - target) <= slack
        if self.operator == "!=":
            return abs(number - target) > slack
        if self.operator == ">":
            return number > target - slack
        if self.operator == ">=":
            return number >= target - slack
        if self.operator == "<":
            return number < target + slack
        return number <= target + slack  # "<="

    def describe(self) -> str:
        text = f"{self.operator} {self.value:g}"
        if self.tolerance:
            text += f" (tolerance ±{self.slack:g})"
        return text

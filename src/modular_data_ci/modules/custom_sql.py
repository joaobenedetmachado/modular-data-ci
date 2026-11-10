"""Custom SQL module settings. The module implementation arrives on Day 4."""

from __future__ import annotations

from pydantic import Field

from modular_data_ci.conditions import Condition
from modular_data_ci.modules.base import ModuleParams


class CustomSqlParams(ModuleParams):
    sql: str = Field(min_length=1)
    """A query returning a single numeric value (first column of the first row)."""
    condition: Condition

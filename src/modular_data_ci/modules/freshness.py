"""Freshness module settings. The module implementation arrives on Day 4."""

from __future__ import annotations

from pydantic import Field

from modular_data_ci.config.types import Duration
from modular_data_ci.modules.base import ModuleParams


class FreshnessParams(ModuleParams):
    table: str = Field(min_length=1)
    timestamp_column: str = Field(min_length=1)
    max_age: Duration
    """Maximum allowed age of the newest row, e.g. ``24h``."""
    where: str | None = None
    """Optional SQL filter applied before taking the newest timestamp."""

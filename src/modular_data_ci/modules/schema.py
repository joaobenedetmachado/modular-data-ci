"""Schema module settings. The module implementation arrives on Day 4."""

from __future__ import annotations

from pydantic import Field

from modular_data_ci.modules.base import ModuleParams


class ColumnSpec(ModuleParams):
    type: str | None = None
    """Expected backend type (case-insensitive), e.g. ``integer``. None skips the type check."""
    required: bool = True
    """The column must exist in the table."""
    nullable: bool = True
    """When False, the column must not contain NULL values."""


class SchemaParams(ModuleParams):
    table: str = Field(min_length=1)
    columns: dict[str, ColumnSpec] = Field(min_length=1)
    allow_extra_columns: bool = True
    """When False, columns not listed in ``columns`` cause a failure."""

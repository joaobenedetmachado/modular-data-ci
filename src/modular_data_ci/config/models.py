"""Top-level configuration schema.

The config layer validates the *shape* of the file (connection, check names,
flags). Module-specific settings are kept as ``CheckConfig.params`` and validated
by the module's own ``params_model``, so new modules never require changes here.
"""

from __future__ import annotations

from collections import Counter
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CHECK_NAME_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*$"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DuckDBConnection(_StrictModel):
    type: Literal["duckdb"]
    path: str = ":memory:"
    read_only: bool = False


class SQLAlchemyConnection(_StrictModel):
    type: Literal["sqlalchemy"]
    url: str = Field(min_length=1)


ConnectionConfig = Annotated[
    DuckDBConnection | SQLAlchemyConnection,
    Field(discriminator="type"),
]


class CheckConfig(BaseModel):
    """One configured check.

    Common keys are declared below. Every other key belongs to the module and is
    exposed through :attr:`params`.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    name: str = Field(pattern=CHECK_NAME_PATTERN, max_length=128)
    module: str = Field(min_length=1)
    enabled: bool = True
    required: bool = True
    """When False, a failure is reported but does not fail the run."""
    description: str | None = None

    @property
    def params(self) -> dict[str, Any]:
        return dict(self.model_extra or {})


class Config(_StrictModel):
    version: Literal[1] = 1
    connection: ConnectionConfig
    checks: list[CheckConfig] = Field(min_length=1)

    @field_validator("checks")
    @classmethod
    def _unique_names(cls, checks: list[CheckConfig]) -> list[CheckConfig]:
        duplicates = sorted(name for name, n in Counter(c.name for c in checks).items() if n > 1)
        if duplicates:
            raise ValueError(f"check names must be unique; duplicated: {', '.join(duplicates)}")
        return checks

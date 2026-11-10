"""Optional execution conditions (``when``) for a check.

All configured parts must hold for the check to run (logical AND). They are
evaluated in order of cost: ``env`` first, then ``depends_on``, then ``sql``.
A check whose conditions do not hold is reported as ``skipped`` with the reason.

    when:
      env:
        GITHUB_REF_NAME: [main, release]   # any of the listed values
        TARGET: prod
      depends_on: [orders_schema]          # those checks must have succeeded
      sql: SELECT COUNT(*) > 0 FROM orders WHERE created_at >= CURRENT_DATE
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from modular_data_ci.connections.base import DataSource
from modular_data_ci.results import CheckStatus

ENV_NAME_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"


def _to_env_string(value: Any) -> str:
    if isinstance(value, bool):  # YAML `CI: true` should match the env value "true"
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value)
    raise ValueError("env values must be a string, number, boolean, or a list of those")


class WhenConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    env: dict[str, tuple[str, ...]] | None = None
    """Each variable must equal one of the listed values."""
    depends_on: tuple[str, ...] | None = None
    """Names of checks, declared earlier in the file, that must end in ``success``."""
    sql: str | None = Field(default=None, min_length=1)
    """Query returning a boolean or number in the first column of the first row."""

    @field_validator("env", mode="before")
    @classmethod
    def _normalize_env(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        normalized: dict[str, tuple[str, ...]] = {}
        for name, expected in value.items():
            values = expected if isinstance(expected, (list, tuple)) else [expected]
            if not values:
                raise ValueError(f"env.{name} needs at least one value")
            normalized[name] = tuple(_to_env_string(v) for v in values)
        return normalized

    @field_validator("env")
    @classmethod
    def _valid_env_names(
        cls, value: dict[str, tuple[str, ...]] | None
    ) -> dict[str, tuple[str, ...]] | None:
        for name in value or {}:
            if not re.match(ENV_NAME_PATTERN, name):
                raise ValueError(f"invalid environment variable name {name!r}")
        return value

    @field_validator("depends_on", mode="before")
    @classmethod
    def _single_dependency(cls, value: Any) -> Any:
        return [value] if isinstance(value, str) else value

    @model_validator(mode="after")
    def _not_empty(self) -> WhenConfig:
        if self.env is None and self.depends_on is None and self.sql is None:
            raise ValueError("'when' needs at least one of 'env', 'depends_on' or 'sql'")
        return self


@dataclass(frozen=True)
class WhenDecision:
    run: bool
    reason: str = ""


RUN = WhenDecision(run=True)


def evaluate_when(
    when: WhenConfig | None,
    *,
    env: Mapping[str, str],
    statuses: Mapping[str, CheckStatus],
    source: DataSource | None = None,
) -> WhenDecision:
    """Decide whether a check should run.

    ``statuses`` maps names of checks that already ran (or were skipped) to their
    status. A query error in ``when.sql`` propagates; the engine reports it as
    ``error`` for the check.
    """
    if when is None:
        return RUN

    for name, allowed in (when.env or {}).items():
        actual = env.get(name)
        if actual is None:
            return WhenDecision(False, f"env {name} is not set")
        if actual not in allowed:
            expected = " or ".join(repr(v) for v in allowed)
            return WhenDecision(False, f"env {name}={actual!r}, expected {expected}")

    for dependency in when.depends_on or ():
        status = statuses.get(dependency)
        if status is None:
            return WhenDecision(False, f"dependency '{dependency}' was not run")
        if status is not CheckStatus.SUCCESS:
            return WhenDecision(False, f"dependency '{dependency}' ended with {status.value}")

    if when.sql is not None:
        if source is None:
            raise RuntimeError("when.sql needs a data source")
        if not _is_true(source.scalar(when.sql)):
            return WhenDecision(False, "when.sql returned false")

    return RUN


def _is_true(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        return value != 0
    raise ValueError(
        f"when.sql must return a boolean or number, got {type(value).__name__}: {value!r}"
    )

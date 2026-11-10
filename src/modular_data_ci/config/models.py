"""Top-level configuration schema.

The config layer validates the *shape* of the file (connection, check names,
flags, execution conditions). Module-specific settings are kept as
``CheckConfig.params`` and validated by the module's own ``params_model``, so new
modules never require changes here.
"""

from __future__ import annotations

from collections import Counter
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from modular_data_ci.config.when import WhenConfig

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


class ModuleSettings(_StrictModel):
    enabled: bool = True
    """When False, every check using this module is skipped."""


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
    when: WhenConfig | None = None

    @property
    def params(self) -> dict[str, Any]:
        return dict(self.model_extra or {})


class Config(_StrictModel):
    version: Literal[1] = 1
    connection: ConnectionConfig
    modules: dict[str, ModuleSettings] = Field(default_factory=dict)
    checks: list[CheckConfig] = Field(min_length=1)

    @field_validator("checks")
    @classmethod
    def _unique_names(cls, checks: list[CheckConfig]) -> list[CheckConfig]:
        duplicates = sorted(name for name, n in Counter(c.name for c in checks).items() if n > 1)
        if duplicates:
            raise ValueError(f"check names must be unique; duplicated: {', '.join(duplicates)}")
        return checks

    @model_validator(mode="after")
    def _dependencies_declared_earlier(self) -> Config:
        position = {check.name: index for index, check in enumerate(self.checks)}
        problems = []
        for index, check in enumerate(self.checks):
            for dependency in (check.when.depends_on or ()) if check.when else ():
                if dependency == check.name:
                    problems.append(f"check '{check.name}' cannot depend on itself")
                elif dependency not in position:
                    problems.append(f"check '{check.name}' depends on unknown check '{dependency}'")
                elif position[dependency] > index:
                    problems.append(
                        f"check '{check.name}' depends on '{dependency}', which is declared "
                        f"later; move '{dependency}' above '{check.name}'"
                    )
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @model_validator(mode="after")
    def _module_settings_are_used(self) -> Config:
        used = {check.module for check in self.checks}
        unused = sorted(set(self.modules) - used)
        if unused:
            raise ValueError(
                f"'modules' lists {', '.join(unused)}, but no check uses "
                f"{'it' if len(unused) == 1 else 'them'} (typo?)"
            )
        return self

    def module_enabled(self, module: str) -> bool:
        settings = self.modules.get(module)
        return settings is None or settings.enabled

    def get_check(self, name: str) -> CheckConfig:
        for check in self.checks:
            if check.name == name:
                return check
        raise KeyError(name)

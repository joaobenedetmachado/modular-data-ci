"""The validation module contract.

A module is a small class with:

* ``name``: the identifier used in YAML (``module: schema``).
* ``params_model``: a Pydantic model describing the module-specific settings.
* ``run(params, context)``: performs the check and returns a :class:`CheckOutcome`.

Modules do not handle timing, ``enabled``/``required`` flags or unexpected
exceptions; the engine does. A module that raises is reported as ``error``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from modular_data_ci.connections.base import DataSource
from modular_data_ci.results import CheckOutcome


class ModuleParams(BaseModel):
    """Base class for module settings. Unknown keys are rejected to catch typos."""

    model_config = ConfigDict(extra="forbid", frozen=True)


ParamsT = TypeVar("ParamsT", bound=ModuleParams)


@dataclass(frozen=True)
class ExecutionContext:
    source: DataSource
    now: datetime
    """The run's reference time (timezone aware). Injected so results are reproducible."""


class ValidationModule(ABC, Generic[ParamsT]):
    name: ClassVar[str]
    params_model: ClassVar[type[ModuleParams]]

    def parse_params(self, raw: Mapping[str, Any]) -> ParamsT:
        return self.params_model.model_validate(dict(raw))  # type: ignore[return-value]

    @abstractmethod
    def run(self, params: ParamsT, context: ExecutionContext) -> CheckOutcome:
        """Run the check against ``context.source``."""

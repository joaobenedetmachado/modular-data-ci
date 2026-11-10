"""Module registry: maps the ``module:`` name in YAML to a module instance.

Sources of modules, in order:

1. Built-in modules shipped with the package.
2. Third-party packages exposing an entry point in the group
   ``modular_data_ci.modules`` that points at a ``ValidationModule`` subclass::

       [project.entry-points."modular_data_ci.modules"]
       row_count = "my_package.checks:RowCountModule"

3. Modules registered in code with :meth:`ModuleRegistry.register`.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Any

from pydantic import ValidationError

from modular_data_ci.config.loader import format_validation_error
from modular_data_ci.config.models import CheckConfig, Config
from modular_data_ci.errors import ConfigError, RegistryError
from modular_data_ci.modules.base import ModuleParams, ValidationModule

ENTRY_POINT_GROUP = "modular_data_ci.modules"
MODULE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class ModuleRegistry:
    def __init__(self, modules: Iterable[type[ValidationModule[Any]]] = ()) -> None:
        self._modules: dict[str, ValidationModule[Any]] = {}
        for module in modules:
            self.register(module)

    @classmethod
    def default(cls) -> ModuleRegistry:
        """Built-in modules plus installed plugins."""
        registry = cls(_builtin_modules())
        registry.load_entry_points()
        return registry

    def register(
        self, module: type[ValidationModule[Any]], *, replace: bool = False
    ) -> ValidationModule[Any]:
        if not (isinstance(module, type) and issubclass(module, ValidationModule)):
            raise RegistryError(f"{module!r} is not a ValidationModule subclass")
        name = getattr(module, "name", None)
        if not isinstance(name, str) or not MODULE_NAME_PATTERN.match(name):
            raise RegistryError(
                f"{module.__name__}.name must be lowercase letters, digits and '_', got {name!r}"
            )
        params_model = getattr(module, "params_model", None)
        if not (isinstance(params_model, type) and issubclass(params_model, ModuleParams)):
            raise RegistryError(f"{module.__name__}.params_model must subclass ModuleParams")
        if name in self._modules and not replace:
            existing = type(self._modules[name])
            raise RegistryError(
                f"module '{name}' is already registered by {existing.__module__}."
                f"{existing.__name__}"
            )
        instance = module()
        self._modules[name] = instance
        return instance

    def load_entry_points(self) -> None:
        for entry_point in entry_points(group=ENTRY_POINT_GROUP):
            try:
                module = entry_point.load()
            except Exception as exc:
                raise RegistryError(
                    f"cannot load module plugin '{entry_point.name}' ({entry_point.value}): {exc}"
                ) from exc
            if getattr(module, "name", None) != entry_point.name:
                raise RegistryError(
                    f"plugin entry point '{entry_point.name}' points at a module named "
                    f"{getattr(module, 'name', None)!r}; the names must match"
                )
            self.register(module)

    def get(self, name: str) -> ValidationModule[Any]:
        try:
            return self._modules[name]
        except KeyError:
            raise LookupError(self._unknown_message(name)) from None

    def names(self) -> list[str]:
        return sorted(self._modules)

    def __contains__(self, name: object) -> bool:
        return name in self._modules

    def __iter__(self) -> Iterator[str]:
        return iter(self.names())

    def __len__(self) -> int:
        return len(self._modules)

    def _unknown_message(self, name: str) -> str:
        message = f"unknown module '{name}'"
        if close := difflib.get_close_matches(name, self._modules, n=1):
            message += f"; did you mean '{close[0]}'?"
        available = ", ".join(self.names()) or "none"
        return f"{message} (available: {available})"


def _builtin_modules() -> list[type[ValidationModule[Any]]]:
    # The four core modules are added on Day 4.
    return []


# --- resolution -------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedCheck:
    check: CheckConfig
    module: ValidationModule[Any]
    params: ModuleParams


def resolve_checks(
    config: Config, registry: ModuleRegistry, *, source: str = "<config>"
) -> dict[str, ResolvedCheck]:
    """Find each check's module and validate its params, before anything runs.

    Every check is resolved, including disabled ones, so a broken check cannot
    hide until the day someone enables it. All problems are reported together.
    """
    resolved: dict[str, ResolvedCheck] = {}
    problems: list[str] = []
    for index, check in enumerate(config.checks):
        prefix = f"checks[{index}] ({check.name})"
        try:
            module = registry.get(check.module)
        except LookupError as exc:
            problems.append(f"{prefix}.module: {exc.args[0]}")
            continue
        try:
            params = module.parse_params(check.params)
        except ValidationError as exc:
            problems.extend(format_validation_error(exc, check.params, prefix=prefix))
            continue
        resolved[check.name] = ResolvedCheck(check=check, module=module, params=params)
    if problems:
        raise ConfigError(source, problems)
    return resolved

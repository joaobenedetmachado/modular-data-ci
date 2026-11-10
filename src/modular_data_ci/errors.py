"""User-facing exceptions."""

from __future__ import annotations

from collections.abc import Iterable


class ModularDataCIError(Exception):
    """Base class for errors that should be shown to the user without a traceback."""


class ConfigError(ModularDataCIError):
    """The configuration file cannot be loaded or is invalid.

    ``problems`` holds one readable line per issue, e.g.
    ``checks[1] (orders_fresh).max_age: invalid duration '1y'``.
    """

    def __init__(self, source: str, problems: Iterable[str]) -> None:
        self.source = source
        self.problems = list(problems)
        super().__init__(self._render())

    def _render(self) -> str:
        header = f"Invalid configuration in {self.source}"
        if len(self.problems) == 1:
            return f"{header}: {self.problems[0]}"
        lines = "\n".join(f"  - {problem}" for problem in self.problems)
        return f"{header} ({len(self.problems)} problems):\n{lines}"


class SelectionError(ModularDataCIError):
    """A check selection (``--only``, ``--skip``, ``--module``) refers to unknown names."""

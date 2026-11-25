"""Decide which configured checks take part in a run.

``plan_checks`` applies, in order:

1. CLI filters (``only``, ``skip``, ``modules``, ``tags``): checks filtered out
   are left out of the run and the report entirely. With ``tags``, a check
   needs at least one of them.
2. ``enabled: false`` on the check, then ``modules.<name>.enabled: false``: these
   checks stay in the report as ``skipped`` with the reason.

``when`` conditions are evaluated later by the engine, because they can depend
on results of earlier checks. A selected check whose dependency was filtered
out is skipped at run time ("dependency ... was not run").
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from modular_data_ci.config.models import CheckConfig, Config
from modular_data_ci.errors import SelectionError


@dataclass(frozen=True)
class PlannedCheck:
    check: CheckConfig
    skip_reason: str | None = None

    @property
    def will_run(self) -> bool:
        return self.skip_reason is None


def plan_checks(
    config: Config,
    *,
    only: Iterable[str] = (),
    skip: Iterable[str] = (),
    modules: Iterable[str] = (),
    tags: Iterable[str] = (),
) -> list[PlannedCheck]:
    only_set, skip_set, module_set, tag_set = set(only), set(skip), set(modules), set(tags)
    _reject_unknown(config, only_set | skip_set, module_set, tag_set)

    planned = []
    for check in config.checks:
        if only_set and check.name not in only_set:
            continue
        if check.name in skip_set:
            continue
        if module_set and check.module not in module_set:
            continue
        if tag_set and not tag_set.intersection(check.tags):
            continue

        if not check.enabled:
            reason: str | None = "disabled in config"
        elif not config.module_enabled(check.module):
            reason = f"module '{check.module}' is disabled in config"
        else:
            reason = None
        planned.append(PlannedCheck(check=check, skip_reason=reason))
    return planned


def _reject_unknown(
    config: Config, names: set[str], modules: set[str], tags: set[str] = frozenset()
) -> None:
    known_names = {check.name for check in config.checks}
    known_modules = {check.module for check in config.checks}
    problems = []
    if unknown := sorted(names - known_names):
        problems.append(f"unknown check(s): {', '.join(unknown)}")
    if unknown := sorted(modules - known_modules):
        problems.append(f"no check uses module(s): {', '.join(unknown)}")
    known_tags = {tag for check in config.checks for tag in check.tags}
    if unknown := sorted(tags - known_tags):
        problems.append(f"no check has tag(s): {', '.join(unknown)}")
    if problems:
        raise SelectionError("; ".join(problems))

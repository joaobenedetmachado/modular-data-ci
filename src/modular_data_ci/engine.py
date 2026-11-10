"""Execution engine shared by the CLI and the GitHub Actions integration.

A run:

1. Resolves every check (module lookup + params validation). Problems raise
   :class:`ConfigError` and nothing runs.
2. Plans the run (CLI filters, ``enabled`` flags).
3. Opens the data source, only if at least one check will run.
4. Runs checks in file order. For each one: skip if planned as skipped, evaluate
   ``when``, call the module, time it, and turn any exception into ``error``.
5. Returns a :class:`RunReport`.

The engine never raises because of a single check: a broken check becomes an
``error`` result and the run continues.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from pydantic_core import to_jsonable_python

from modular_data_ci import __version__
from modular_data_ci.config.models import Config
from modular_data_ci.config.selection import PlannedCheck, plan_checks
from modular_data_ci.config.when import evaluate_when
from modular_data_ci.connections import DataSource, open_source
from modular_data_ci.errors import DataSourceError
from modular_data_ci.modules.base import ExecutionContext
from modular_data_ci.registry import ModuleRegistry, ResolvedCheck, resolve_checks
from modular_data_ci.results import CheckOutcome, CheckResult, CheckStatus, RunReport

SourceFactory = Callable[[Config], DataSource]
Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _open_from_config(config: Config) -> DataSource:
    return open_source(config.connection)


class Engine:
    def __init__(
        self,
        registry: ModuleRegistry | None = None,
        *,
        source_factory: SourceFactory = _open_from_config,
        clock: Clock = _utc_now,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.registry = registry if registry is not None else ModuleRegistry.default()
        self.source_factory = source_factory
        self.clock = clock
        self.env = env

    def run(
        self,
        config: Config,
        *,
        only: Iterable[str] = (),
        skip: Iterable[str] = (),
        modules: Iterable[str] = (),
        config_path: str | None = None,
    ) -> RunReport:
        resolved = resolve_checks(config, self.registry, source=config_path or "<config>")
        plan = plan_checks(config, only=only, skip=skip, modules=modules)

        started_at = self.clock()
        if started_at.tzinfo is None:
            raise ValueError("the engine clock must return timezone-aware datetimes")
        env = os.environ if self.env is None else self.env

        source: DataSource | None = None
        source_error: str | None = None
        if any(p.will_run for p in plan):
            try:
                source = self.source_factory(config)
            except DataSourceError as exc:
                source_error = str(exc)

        results: list[CheckResult] = []
        statuses: dict[str, CheckStatus] = {}
        try:
            for planned in plan:
                result = self._run_one(
                    planned,
                    resolved[planned.check.name],
                    source=source,
                    source_error=source_error,
                    env=env,
                    statuses=statuses,
                    now=started_at,
                )
                results.append(result)
                statuses[result.name] = result.status
        finally:
            if source is not None:
                source.close()

        return RunReport(
            tool_version=__version__,
            started_at=started_at,
            finished_at=self.clock(),
            config_path=config_path,
            results=results,
        )

    def _run_one(
        self,
        planned: PlannedCheck,
        resolved: ResolvedCheck,
        *,
        source: DataSource | None,
        source_error: str | None,
        env: Mapping[str, str],
        statuses: Mapping[str, CheckStatus],
        now: datetime,
    ) -> CheckResult:
        check = planned.check
        start = time.perf_counter()

        def finish(outcome: CheckOutcome) -> CheckResult:
            return CheckResult(
                name=check.name,
                module=check.module,
                status=outcome.status,
                required=check.required,
                message=outcome.message,
                details=to_jsonable_python(outcome.details, fallback=str),
                duration_ms=round((time.perf_counter() - start) * 1000, 3),
            )

        if planned.skip_reason is not None:
            return finish(CheckOutcome.skipped(planned.skip_reason))

        if source is None:
            return finish(CheckOutcome.error(source_error or "no data source available"))

        try:
            decision = evaluate_when(check.when, env=env, statuses=statuses, source=source)
        except Exception as exc:
            return finish(CheckOutcome.error(f"when condition failed: {_describe(exc)}"))
        if not decision.run:
            return finish(CheckOutcome.skipped(decision.reason))

        context = ExecutionContext(source=source, now=now)
        try:
            outcome: Any = resolved.module.run(resolved.params, context)
        except Exception as exc:
            return finish(CheckOutcome.error(_describe(exc), exception_type=type(exc).__name__))
        if not isinstance(outcome, CheckOutcome):
            return finish(
                CheckOutcome.error(
                    f"module '{check.module}' returned {type(outcome).__name__}, "
                    "expected CheckOutcome"
                )
            )
        return finish(outcome)


def _describe(exc: BaseException) -> str:
    message = str(exc).strip()
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__

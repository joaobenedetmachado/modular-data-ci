"""Standardized result models shared by the engine, modules and reporters."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

EXIT_OK = 0
"""All required checks passed."""
EXIT_CHECKS_FAILED = 1
"""At least one required check ended in ``failure`` or ``error``."""
EXIT_USAGE_ERROR = 2
"""Invalid arguments or invalid configuration; no checks were run."""


class CheckStatus(str, Enum):
    SUCCESS = "success"
    """The data met the check's expectation."""
    FAILURE = "failure"
    """The check ran and the data did not meet the expectation."""
    SKIPPED = "skipped"
    """The check was not run (disabled or its condition was not met)."""
    ERROR = "error"
    """The check could not complete (bad SQL, missing table, unexpected exception)."""


BLOCKING_STATUSES = frozenset({CheckStatus.FAILURE, CheckStatus.ERROR})


class CheckOutcome(BaseModel):
    """What a validation module returns. The engine wraps it into a :class:`CheckResult`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: CheckStatus
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def success(cls, message: str = "", **details: Any) -> CheckOutcome:
        return cls(status=CheckStatus.SUCCESS, message=message, details=details)

    @classmethod
    def failure(cls, message: str, **details: Any) -> CheckOutcome:
        return cls(status=CheckStatus.FAILURE, message=message, details=details)

    @classmethod
    def skipped(cls, message: str, **details: Any) -> CheckOutcome:
        return cls(status=CheckStatus.SKIPPED, message=message, details=details)

    @classmethod
    def error(cls, message: str, **details: Any) -> CheckOutcome:
        return cls(status=CheckStatus.ERROR, message=message, details=details)


class CheckResult(BaseModel):
    """The final, reportable result of one configured check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    module: str
    status: CheckStatus
    required: bool = True
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = Field(default=0.0, ge=0)

    @property
    def blocking(self) -> bool:
        """True when this result should make the run (and CI) fail."""
        return self.required and self.status in BLOCKING_STATUSES


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    total: int
    success: int
    failure: int
    skipped: int
    error: int
    blocking: int


class RunReport(BaseModel):
    """Everything produced by one run. Serialized as the JSON report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_version: str
    started_at: datetime
    finished_at: datetime
    config_path: str | None = None
    results: list[CheckResult] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def summary(self) -> RunSummary:
        counts = {status: 0 for status in CheckStatus}
        for result in self.results:
            counts[result.status] += 1
        return RunSummary(
            total=len(self.results),
            success=counts[CheckStatus.SUCCESS],
            failure=counts[CheckStatus.FAILURE],
            skipped=counts[CheckStatus.SKIPPED],
            error=counts[CheckStatus.ERROR],
            blocking=sum(1 for r in self.results if r.blocking),
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def passed(self) -> bool:
        return not any(r.blocking for r in self.results)

    @property
    def exit_code(self) -> int:
        return EXIT_OK if self.passed else EXIT_CHECKS_FAILED

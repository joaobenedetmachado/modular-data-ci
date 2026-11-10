"""Shows that a module can be written against the contract alone."""

from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from modular_data_ci.conditions import Condition
from modular_data_ci.connections import DataSource
from modular_data_ci.modules import ExecutionContext, ModuleParams, ValidationModule
from modular_data_ci.results import CheckOutcome, CheckStatus
from tests.fakes import FakeSource


class RowCountParams(ModuleParams):
    table: str
    condition: Condition


class RowCountModule(ValidationModule[RowCountParams]):
    name = "row_count"
    params_model = RowCountParams

    def run(self, params: RowCountParams, context: ExecutionContext) -> CheckOutcome:
        count = context.source.scalar(f"SELECT COUNT(*) FROM {params.table}")
        if params.condition.evaluate(count):
            return CheckOutcome.success(f"{count} rows", row_count=count)
        return CheckOutcome.failure(
            f"{count} rows, expected {params.condition.describe()}", row_count=count
        )


def _context(value: Any) -> ExecutionContext:
    source: DataSource = FakeSource(value)
    return ExecutionContext(source=source, now=datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_module_parses_params_and_succeeds():
    module = RowCountModule()
    params = module.parse_params({"table": "orders", "condition": "> 0"})
    outcome = module.run(params, _context(5))
    assert outcome.status is CheckStatus.SUCCESS
    assert outcome.details == {"row_count": 5}


def test_module_reports_failure_with_details():
    module = RowCountModule()
    params = module.parse_params({"table": "orders", "condition": "> 0"})
    outcome = module.run(params, _context(0))
    assert outcome.status is CheckStatus.FAILURE
    assert "expected > 0" in outcome.message


def test_module_params_reject_unknown_keys():
    with pytest.raises(ValidationError):
        RowCountModule().parse_params({"table": "t", "condition": "> 0", "tabel": "x"})


def test_module_without_run_cannot_be_instantiated():
    class Incomplete(ValidationModule[RowCountParams]):
        name = "incomplete"
        params_model = RowCountParams

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]

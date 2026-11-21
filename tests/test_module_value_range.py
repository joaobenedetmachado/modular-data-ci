import pytest
from pydantic import ValidationError

from modular_data_ci.modules.value_range import ValueRangeModule
from modular_data_ci.results import CheckStatus
from tests.module_fixtures import run_module


def test_out_of_range_rows(users):
    outcome = run_module(ValueRangeModule, users, table="users", column="age", min=18, max=65)
    assert outcome.status is CheckStatus.FAILURE
    assert outcome.message == "1 row(s) with age outside in [18, 65] (found 17..17)"


def test_in_range_and_nulls_ignored(users):
    outcome = run_module(ValueRangeModule, users, table="users", column="age", min=17)
    assert outcome.status is CheckStatus.SUCCESS
    assert outcome.message == "all age values in [17, inf]"


def test_exclusive_bounds(users):
    outcome = run_module(
        ValueRangeModule, users, table="users", column="age", min=17, inclusive=False
    )
    assert outcome.status is CheckStatus.FAILURE


def test_needs_a_bound():
    with pytest.raises(ValidationError):
        ValueRangeModule().parse_params({"table": "t", "column": "c"})

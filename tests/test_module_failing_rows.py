from modular_data_ci.modules.failing_rows import FailingRowsModule
from modular_data_ci.results import CheckStatus
from tests.module_fixtures import run_module


def test_failing_rows_with_sample(users):
    outcome = run_module(FailingRowsModule, users, sql="SELECT id, age FROM users WHERE age < 18;")
    assert outcome.status is CheckStatus.FAILURE
    assert outcome.message == "1 failing row(s), expected at most 0"
    assert outcome.details["sample"] == [[4, 17]]


def test_no_rows_and_limit(users):
    none = run_module(FailingRowsModule, users, sql="SELECT * FROM users WHERE age > 99")
    assert none.message == "no failing rows"
    tolerated = run_module(
        FailingRowsModule, users, sql="SELECT * FROM users WHERE age IS NULL", max_rows=1
    )
    assert tolerated.status is CheckStatus.SUCCESS

from modular_data_ci.modules.not_null import NotNullModule
from modular_data_ci.results import CheckStatus
from tests.module_fixtures import run_module


def test_passes_on_complete_columns(users):
    outcome = run_module(NotNullModule, users, table="users", columns=["id", "country"])
    assert outcome.status is CheckStatus.SUCCESS
    assert outcome.details["null_counts"] == {"id": 0, "country": 0}


def test_fails_and_names_columns(users):
    outcome = run_module(NotNullModule, users, table="users", columns=["id", "email", "age"])
    assert outcome.status is CheckStatus.FAILURE
    assert outcome.message == "NULL values in email (1), age (1)"


def test_max_nulls_and_where(users):
    assert (
        run_module(NotNullModule, users, table="users", columns=["email"], max_nulls=1).status
        is CheckStatus.SUCCESS
    )
    assert (
        run_module(
            NotNullModule, users, table="users", columns=["email"], where="country = 'US'"
        ).status
        is CheckStatus.SUCCESS
    )

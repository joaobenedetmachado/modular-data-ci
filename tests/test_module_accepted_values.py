from modular_data_ci.modules.accepted_values import AcceptedValuesModule
from modular_data_ci.results import CheckStatus
from tests.module_fixtures import run_module


def test_unexpected_values_reported(users):
    outcome = run_module(
        AcceptedValuesModule, users, table="users", column="country", values=["BR", "US"]
    )
    assert outcome.status is CheckStatus.FAILURE
    assert outcome.message == "1 row(s) with unexpected country: XX"
    assert outcome.details["unexpected_values"] == {"XX": 1}


def test_all_values_accepted(users):
    outcome = run_module(
        AcceptedValuesModule, users, table="users", column="country", values=["BR", "US", "XX"]
    )
    assert outcome.status is CheckStatus.SUCCESS


def test_null_handling(users):
    params = {"table": "users", "column": "age", "values": [30, 41, 17, 25]}
    assert run_module(AcceptedValuesModule, users, **params).status is CheckStatus.SUCCESS
    strict = run_module(AcceptedValuesModule, users, allow_null=False, **params)
    assert strict.status is CheckStatus.FAILURE
    assert strict.details["unexpected_values"] == {"None": 1}

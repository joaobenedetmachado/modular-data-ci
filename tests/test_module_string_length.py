from modular_data_ci.modules.string_length import StringLengthModule
from modular_data_ci.results import CheckStatus
from tests.module_fixtures import run_module


def test_country_codes_are_two_letters(users):
    outcome = run_module(
        StringLengthModule, users, table="users", column="country", min_length=2, max_length=2
    )
    assert outcome.status is CheckStatus.SUCCESS


def test_too_short(users):
    outcome = run_module(StringLengthModule, users, table="users", column="email", min_length=8)
    assert outcome.status is CheckStatus.FAILURE
    assert outcome.message == "4 row(s) with email length outside bounds (found lengths 7..7)"

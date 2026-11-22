import pytest
from pydantic import ValidationError

from modular_data_ci.modules.pattern import PatternModule
from modular_data_ci.results import CheckStatus
from tests.module_fixtures import run_module

EMAIL = r"[^@\s]+@[^@\s]+\.[a-z]+"


def test_matching_values(users):
    outcome = run_module(PatternModule, users, table="users", column="email", regex=EMAIL)
    assert outcome.status is CheckStatus.SUCCESS


def test_full_match_required(users):
    outcome = run_module(PatternModule, users, table="users", column="country", regex="B")
    assert outcome.status is CheckStatus.FAILURE
    assert outcome.details["invalid_rows"] == 5
    assert outcome.details["sample"] == ["BR", "US", "XX"]


def test_python_fallback_matches_sql(users, monkeypatch):
    monkeypatch.setattr(users.source, "dialect", "sqlite")
    outcome = run_module(PatternModule, users, table="users", column="country", regex="B.")
    assert outcome.status is CheckStatus.FAILURE
    assert outcome.details["invalid_rows"] == 3
    assert outcome.details["sample"] == ["US", "XX"]


def test_invalid_regex_rejected():
    with pytest.raises(ValidationError, match="invalid regular expression"):
        PatternModule().parse_params({"table": "t", "column": "c", "regex": "("})

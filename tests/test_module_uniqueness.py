from modular_data_ci.modules.uniqueness import UniquenessModule
from modular_data_ci.results import CheckStatus
from tests.module_fixtures import make_context, run_module


def test_detects_duplicates_with_sample(users):
    outcome = run_module(UniquenessModule, users, table="users", columns="id")
    assert outcome.status is CheckStatus.FAILURE
    assert outcome.message == "1 duplicated value(s) of (id) across 2 rows"
    assert outcome.details["sample"] == [{"id": 4, "count": 2}]


def test_composite_key_is_unique(users):
    outcome = run_module(UniquenessModule, users, table="users", columns=["id", "email"])
    assert outcome.status is CheckStatus.SUCCESS


def test_nulls_ignored_by_default():
    ctx = make_context("CREATE TABLE t AS SELECT NULL::INT AS k FROM range(3)")
    assert run_module(UniquenessModule, ctx, table="t", columns=["k"]).status is CheckStatus.SUCCESS
    strict = run_module(UniquenessModule, ctx, table="t", columns=["k"], ignore_nulls=False)
    assert strict.status is CheckStatus.FAILURE


def test_sample_can_be_disabled(users):
    outcome = run_module(UniquenessModule, users, table="users", columns=["id"], sample_size=0)
    assert "sample" not in outcome.details

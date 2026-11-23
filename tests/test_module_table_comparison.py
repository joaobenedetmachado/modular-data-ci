import pytest
from pydantic import ValidationError

from modular_data_ci.modules.table_comparison import TableComparisonModule
from modular_data_ci.results import CheckStatus
from tests.module_fixtures import make_context, run_module


@pytest.fixture
def ctx():
    return make_context(
        "CREATE TABLE staging AS SELECT range AS id, range * 1.0 AS v FROM range(100)",
        "CREATE TABLE prod AS SELECT * FROM staging WHERE id < 97",
    )


def test_counts_differ(ctx):
    outcome = run_module(
        TableComparisonModule, ctx, source={"table": "staging"}, target={"table": "prod"}
    )
    assert outcome.status is CheckStatus.FAILURE
    assert outcome.message == "count: staging=100, prod=97 (difference -3, allowed ±0)"


def test_tolerance_and_where(ctx):
    sides = {"source": {"table": "staging"}, "target": {"table": "prod"}}
    tolerant = run_module(TableComparisonModule, ctx, tolerance={"relative": 0.05}, **sides)
    assert tolerant.status is CheckStatus.SUCCESS
    filtered = run_module(
        TableComparisonModule,
        ctx,
        source={"table": "staging", "where": "id < 97"},
        target={"table": "prod"},
        function="sum",
        column="v",
    )
    assert filtered.status is CheckStatus.SUCCESS


def test_column_required():
    with pytest.raises(ValidationError):
        TableComparisonModule().parse_params(
            {"source": {"table": "a"}, "target": {"table": "b"}, "function": "sum"}
        )

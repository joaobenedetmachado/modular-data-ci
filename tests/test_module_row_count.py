import pytest
from pydantic import ValidationError

from modular_data_ci.modules.row_count import RowCountModule
from modular_data_ci.results import CheckStatus
from tests.module_fixtures import run_module, users  # noqa: F401


@pytest.mark.parametrize(
    ("params", "status"),
    [
        ({"min": 5}, CheckStatus.SUCCESS),
        ({"min": 6}, CheckStatus.FAILURE),
        ({"max": 4}, CheckStatus.FAILURE),
        ({"min": 1, "max": 5}, CheckStatus.SUCCESS),
        ({"min": 1, "where": "country = 'BR'", "max": 2}, CheckStatus.SUCCESS),
    ],
)
def test_row_count(users, params, status):  # noqa: F811
    outcome = run_module(RowCountModule, users, table="users", **params)
    assert outcome.status is status
    assert outcome.details["row_count"] in (5, 2)


def test_messages(users):  # noqa: F811
    assert run_module(RowCountModule, users, table="users", min=10).message == (
        "5 rows, expected at least 10"
    )


@pytest.mark.parametrize("params", [{}, {"min": 3, "max": 1}, {"min": -1}])
def test_invalid_params(params):
    with pytest.raises(ValidationError):
        RowCountModule().parse_params({"table": "t", **params})

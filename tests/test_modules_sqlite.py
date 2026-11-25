"""The newer modules against SQLite through SQLAlchemy (another dialect than DuckDB)."""

import pytest

from modular_data_ci.connections.sqlalchemy_source import SQLAlchemySource
from modular_data_ci.modules import ExecutionContext
from modular_data_ci.modules.accepted_values import AcceptedValuesModule
from modular_data_ci.modules.not_null import NotNullModule
from modular_data_ci.modules.row_count import RowCountModule
from modular_data_ci.modules.uniqueness import UniquenessModule
from modular_data_ci.modules.value_range import ValueRangeModule
from modular_data_ci.results import CheckStatus
from tests.module_fixtures import NOW, run_module


@pytest.fixture
def sqlite(tmp_path):
    source = SQLAlchemySource(f"sqlite:///{tmp_path / 'db.sqlite'}")
    source.query("CREATE TABLE users (id INTEGER, email TEXT, country TEXT, age INTEGER)")
    source.query(
        "INSERT INTO users VALUES (1, 'a@x.com', 'BR', 30), (2, 'b@x.com', 'US', 41), "
        "(3, NULL, 'BR', NULL), (4, 'd@x.com', 'XX', 17), (4, 'e@x.com', 'US', 25)"
    )
    yield ExecutionContext(source=source, now=NOW)
    source.close()


@pytest.mark.parametrize(
    ("module", "params", "status"),
    [
        (RowCountModule, {"table": "users", "min": 5, "max": 5}, CheckStatus.SUCCESS),
        (NotNullModule, {"table": "users", "columns": ["email"]}, CheckStatus.FAILURE),
        (UniquenessModule, {"table": "users", "columns": ["id"]}, CheckStatus.FAILURE),
        (
            AcceptedValuesModule,
            {"table": "users", "column": "country", "values": ["BR", "US"]},
            CheckStatus.FAILURE,
        ),
        (ValueRangeModule, {"table": "users", "column": "age", "min": 17}, CheckStatus.SUCCESS),
    ],
)
def test_basic_modules_on_sqlite(sqlite, module, params, status):
    assert run_module(module, sqlite, **params).status is status


def test_pattern_uses_python_fallback_on_sqlite(sqlite):
    from modular_data_ci.modules.pattern import PatternModule

    outcome = run_module(PatternModule, sqlite, table="users", column="country", regex="BR|US")
    assert outcome.status is CheckStatus.FAILURE
    assert outcome.details["sample"] == ["XX"]


def test_relational_modules_on_sqlite(sqlite):
    from modular_data_ci.modules.failing_rows import FailingRowsModule
    from modular_data_ci.modules.referential_integrity import ReferentialIntegrityModule
    from modular_data_ci.modules.string_length import StringLengthModule
    from modular_data_ci.modules.table_comparison import TableComparisonModule

    sqlite.source.query("CREATE TABLE countries (code TEXT)")
    sqlite.source.query("INSERT INTO countries VALUES ('BR'), ('US')")
    orphan = run_module(
        ReferentialIntegrityModule,
        sqlite,
        table="users",
        column="country",
        references={"table": "countries", "column": "code"},
    )
    assert orphan.details["sample"] == ["XX"]
    rows = run_module(FailingRowsModule, sqlite, sql="SELECT id FROM users WHERE age < 18")
    assert rows.details["sample"] == [[4]]
    length = run_module(StringLengthModule, sqlite, table="users", column="country", max_length=2)
    assert length.status is CheckStatus.SUCCESS
    compare = run_module(
        TableComparisonModule, sqlite, source={"table": "countries"}, target={"table": "users"}
    )
    assert compare.details["difference"] == 3

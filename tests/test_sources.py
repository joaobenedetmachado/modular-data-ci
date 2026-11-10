"""The same contract tests run against DuckDB and SQLAlchemy (SQLite)."""

from datetime import datetime
from pathlib import Path

import duckdb
import pytest

from modular_data_ci.config import DuckDBConnection, SQLAlchemyConnection
from modular_data_ci.connections import open_source, split_identifier
from modular_data_ci.connections.duckdb_source import DuckDBSource
from modular_data_ci.connections.sqlalchemy_source import SQLAlchemySource
from modular_data_ci.errors import DataSourceError

SETUP = [
    "CREATE TABLE orders ("
    'order_id INTEGER NOT NULL, amount DOUBLE, created_at TIMESTAMP, "Order" INTEGER)',
    "INSERT INTO orders VALUES "
    "(1, 10.5, '2026-03-01 10:00:00', 7), (2, 20.0, '2026-03-02 09:00:00', 8)",
]


@pytest.fixture(params=["duckdb", "sqlalchemy"])
def source(request, tmp_path: Path):
    if request.param == "duckdb":
        path = tmp_path / "test.duckdb"
        with duckdb.connect(str(path)) as conn:
            for statement in SETUP:
                conn.execute(statement)
        src = open_source(DuckDBConnection(type="duckdb", path=str(path)))
    else:
        url = f"sqlite:///{tmp_path / 'test.sqlite'}"
        import sqlalchemy as sa

        engine = sa.create_engine(url)
        with engine.begin() as conn:
            for statement in SETUP:
                conn.exec_driver_sql(statement.replace("DOUBLE", "REAL"))
        engine.dispose()
        src = open_source(SQLAlchemyConnection(type="sqlalchemy", url=url))
    yield src
    src.close()


def test_query_and_scalar(source):
    assert source.query("SELECT order_id FROM orders ORDER BY order_id") == [(1,), (2,)]
    assert source.scalar("SELECT SUM(amount) FROM orders") == pytest.approx(30.5)
    assert source.scalar("SELECT order_id FROM orders WHERE 1 = 0") is None


def test_named_parameters_with_placeholder(source):
    sql = f"SELECT COUNT(*) FROM orders WHERE amount > {source.placeholder('minimum')}"
    assert source.scalar(sql, {"minimum": 15}) == 1


def test_timestamp_parameter(source):
    sql = (
        f"SELECT COUNT(*) FROM {source.quote('orders')} "
        f"WHERE {source.quote('created_at')} >= {source.placeholder('since')}"
    )
    since = datetime(2026, 3, 2)
    value = since if source.dialect == "duckdb" else since.isoformat(sep=" ")
    assert source.scalar(sql, {"since": value}) == 1


def test_quote_handles_mixed_case_and_reserved_names(source):
    assert source.scalar(f"SELECT SUM({source.quote('Order')}) FROM {source.quote('orders')}") == 15


def test_columns(source):
    columns = {c.name: c for c in source.columns("orders")}
    assert list(columns) == ["order_id", "amount", "created_at", "Order"]
    assert columns["order_id"].type.upper().startswith("INT")
    assert columns["order_id"].nullable is False
    assert columns["amount"].nullable is True


def test_missing_table_raises_lookup_error(source):
    with pytest.raises(LookupError, match="table 'nope' not found"):
        source.columns("nope")


def test_failed_query_does_not_break_the_next_one(source):
    with pytest.raises(Exception, match=r"(?i)nope"):
        source.query("SELECT * FROM nope")
    assert source.scalar("SELECT COUNT(*) FROM orders") == 2


# --- DuckDB specifics -------------------------------------------------------


def test_duckdb_missing_file_is_an_error_not_a_new_database(tmp_path: Path):
    path = tmp_path / "missing.duckdb"
    with pytest.raises(DataSourceError, match="file not found"):
        DuckDBSource(str(path))
    assert not path.exists()


def test_duckdb_schema_qualified_columns():
    conn = duckdb.connect()
    conn.execute("CREATE SCHEMA analytics")
    conn.execute("CREATE TABLE analytics.events (id INTEGER)")
    source = DuckDBSource.from_connection(conn)
    assert [c.name for c in source.columns("analytics.events")] == ["id"]
    assert source.quote("analytics.events") == '"analytics"."events"'
    with pytest.raises(LookupError):
        source.columns("events")


def test_duckdb_quote_escapes_quotes():
    source = DuckDBSource.from_connection(duckdb.connect())
    assert source.quote('we"ird') == '"we""ird"'


# --- SQLAlchemy specifics ---------------------------------------------------


def test_sqlalchemy_connection_error_hides_password():
    with pytest.raises(DataSourceError) as exc:
        SQLAlchemySource("postgresql+nosuchdriver://user:s3cret@localhost/db")
    assert "s3cret" not in str(exc.value)
    assert "***" in str(exc.value)


@pytest.mark.parametrize("name", ["", "a..b", ".a", "a.b.c.d"])
def test_split_identifier_rejects_invalid_names(name):
    with pytest.raises(ValueError, match="invalid table name"):
        split_identifier(name)

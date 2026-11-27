import pytest

from modular_data_ci.config.models import DuckDBConnection
from modular_data_ci.connections import open_source
from modular_data_ci.errors import DataSourceError


def test_views_over_csv_and_parquet(tmp_path):
    csv = tmp_path / "orders.csv"
    csv.write_text("id,amount\n1,10\n2,20\n")
    parquet = tmp_path / "customers.parquet"
    source = open_source(DuckDBConnection(type="duckdb"))
    source.query(f"COPY (SELECT 1 AS id) TO '{parquet}' (FORMAT parquet)")
    source.close()

    source = open_source(
        DuckDBConnection(
            type="duckdb",
            files={"orders": str(csv), "customers": str(parquet)},
            setup=["CREATE MACRO double_it(x) AS x * 2"],
        )
    )
    assert source.scalar("SELECT SUM(amount) FROM orders") == 30
    assert source.scalar("SELECT double_it(id) FROM customers") == 2
    assert [c.name for c in source.columns("orders")] == ["id", "amount"]
    source.close()


def test_missing_file_and_bad_setup(tmp_path):
    with pytest.raises(DataSourceError, match=r"connection.files.t: file not found"):
        open_source(DuckDBConnection(type="duckdb", files={"t": str(tmp_path / "no.csv")}))
    with pytest.raises(DataSourceError, match=r"connection.setup\[0\] failed"):
        open_source(DuckDBConnection(type="duckdb", setup=["SELEC 1"]))


def test_invalid_view_name():
    with pytest.raises(ValueError, match="invalid view name"):
        DuckDBConnection(type="duckdb", files={"bad name": "x.csv"})

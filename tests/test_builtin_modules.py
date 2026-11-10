"""Module-level tests for the four built-in modules, against DuckDB."""

from datetime import datetime, timedelta, timezone

import duckdb
import pytest

from modular_data_ci.connections.duckdb_source import DuckDBSource
from modular_data_ci.modules import ExecutionContext
from modular_data_ci.modules._sql import format_duration, to_utc_datetime
from modular_data_ci.modules.aggregation import AggregationModule
from modular_data_ci.modules.custom_sql import CustomSqlModule
from modular_data_ci.modules.freshness import FreshnessModule
from modular_data_ci.modules.schema import SchemaModule, types_match
from modular_data_ci.registry import ModuleRegistry
from modular_data_ci.results import CheckStatus

NOW = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def context():
    conn = duckdb.connect()
    conn.execute(
        """
        CREATE TABLE orders (
            order_id INTEGER NOT NULL,
            amount DECIMAL(10, 2),
            created_at TIMESTAMP,
            note VARCHAR
        )
        """
    )
    # 3 orders in the last day, 2 in the day before, 1 older; one NULL amount.
    conn.execute(
        """
        INSERT INTO orders VALUES
            (1, 10.00, '2026-03-10 11:00:00', 'a'),
            (2, 20.00, '2026-03-10 01:00:00', NULL),
            (3, NULL,  '2026-03-09 13:00:00', 'c'),
            (4, 40.00, '2026-03-09 11:00:00', 'd'),
            (5, 50.00, '2026-03-08 20:00:00', 'e'),
            (6, 60.00, '2026-03-01 00:00:00', 'f')
        """
    )
    yield ExecutionContext(source=DuckDBSource.from_connection(conn), now=NOW)
    conn.close()


def _run(module_cls, context, **params):
    module = module_cls()
    return module.run(module.parse_params(params), context)


def test_builtins_are_registered_by_default():
    assert ModuleRegistry.default().names() == ["aggregation", "custom_sql", "freshness", "schema"]


# --- schema -----------------------------------------------------------------


def test_schema_success(context):
    outcome = _run(
        SchemaModule,
        context,
        table="orders",
        columns={
            "order_id": {"type": "int", "nullable": False},
            "amount": {"type": "decimal(10,2)"},
            "created_at": {"type": "timestamp"},
            "note": {"type": "text"},
        },
        allow_extra_columns=False,
    )
    assert outcome.status is CheckStatus.SUCCESS, outcome.message
    assert outcome.details["actual_columns"]["amount"] == "DECIMAL(10,2)"
    assert outcome.details["null_counts"] == {"order_id": 0}


def test_schema_reports_every_problem(context):
    outcome = _run(
        SchemaModule,
        context,
        table="orders",
        columns={
            "order_id": {"type": "varchar"},
            "amount": {"nullable": False},
            "customer_id": {},
            "optional_col": {"required": False},
        },
        allow_extra_columns=False,
    )
    assert outcome.status is CheckStatus.FAILURE
    assert outcome.details["problems"] == [
        "column 'order_id' is INTEGER, expected varchar",
        "column 'amount' has 1 NULL value(s)",
        "missing column 'customer_id'",
        "unexpected column(s): created_at, note",
    ]
    assert outcome.message.startswith("4 schema problem(s): ")


def test_schema_column_names_are_case_insensitive(context):
    outcome = _run(SchemaModule, context, table="orders", columns={"ORDER_ID": {"type": "integer"}})
    assert outcome.status is CheckStatus.SUCCESS


def test_schema_missing_table_is_a_failure(context):
    outcome = _run(SchemaModule, context, table="nope", columns={"a": {}})
    assert outcome.status is CheckStatus.FAILURE
    assert outcome.message == "table 'nope' not found"


@pytest.mark.parametrize(
    ("expected", "actual", "match"),
    [
        ("integer", "INT4", True),
        ("int", "INTEGER", True),
        ("bigint", "INTEGER", False),
        ("varchar", "VARCHAR(255)", True),
        ("varchar(255)", "VARCHAR(100)", False),
        ("decimal(18, 2)", "NUMERIC(18,2)", True),
        ("double", "DOUBLE PRECISION", True),
        ("timestamp", "TIMESTAMP WITHOUT TIME ZONE", True),
        ("timestamp", "TIMESTAMP WITH TIME ZONE", False),
        ("text", "character varying", True),
    ],
)
def test_types_match(expected, actual, match):
    assert types_match(expected, actual) is match


# --- freshness --------------------------------------------------------------


def test_freshness_success(context):
    outcome = _run(
        FreshnessModule, context, table="orders", timestamp_column="created_at", max_age="2h"
    )
    assert outcome.status is CheckStatus.SUCCESS
    assert outcome.message == "newest row is 1h old"
    assert outcome.details["age_seconds"] == 3600


def test_freshness_failure(context):
    outcome = _run(
        FreshnessModule, context, table="orders", timestamp_column="created_at", max_age="30m"
    )
    assert outcome.status is CheckStatus.FAILURE
    assert outcome.message == "newest row is 1h old, expected at most 30m"


def test_freshness_where_filter(context):
    outcome = _run(
        FreshnessModule,
        context,
        table="orders",
        timestamp_column="created_at",
        max_age="1d",
        where="note = 'f'",
    )
    assert outcome.status is CheckStatus.FAILURE
    assert "9d 12h old" in outcome.message


def test_freshness_no_rows(context):
    outcome = _run(
        FreshnessModule,
        context,
        table="orders",
        timestamp_column="created_at",
        max_age="1d",
        where="1 = 0",
    )
    assert outcome.status is CheckStatus.FAILURE
    assert outcome.message.startswith("no rows")


def test_freshness_missing_column_raises(context):
    # The engine turns this into an `error` result.
    with pytest.raises(duckdb.Error):
        _run(FreshnessModule, context, table="orders", timestamp_column="nope", max_age="1d")


# --- aggregation ------------------------------------------------------------


def test_aggregation_whole_table(context):
    outcome = _run(
        AggregationModule, context, table="orders", function="sum", column="amount",
        condition="== 180",
    )  # fmt: skip
    assert outcome.status is CheckStatus.SUCCESS, outcome.message
    assert outcome.message == "sum(amount) = 180 == 180"


@pytest.mark.parametrize(
    ("function", "column", "expected"),
    [
        ("count", None, 3),
        ("count", "amount", 2),
        ("count_distinct", "note", 1),
        ("sum", "amount", 30),
        ("avg", "amount", 15),
        ("min", "amount", 10),
        ("max", "amount", 20),
    ],
)
def test_aggregation_functions_over_period(context, function, column, expected):
    outcome = _run(
        AggregationModule,
        context,
        table="orders",
        function=function,
        column=column,
        period={"column": "created_at", "window": "1d"},
        condition=f"== {expected}",
        **({"where": "note IS NULL OR note = 'a'"} if function == "count_distinct" else {}),
    )
    assert outcome.status is CheckStatus.SUCCESS, outcome.message


def test_aggregation_tolerance(context):
    params = dict(table="orders", function="sum", column="amount")
    within = {"operator": "==", "value": 190, "tolerance": {"relative": 0.06}}
    outside = {"operator": "==", "value": 190, "tolerance": {"relative": 0.05}}
    assert _run(AggregationModule, context, **params, condition=within).status.value == "success"
    failed = _run(AggregationModule, context, **params, condition=outside)
    assert failed.status is CheckStatus.FAILURE
    assert failed.message == "sum(amount) = 180, expected == 190 (tolerance ±9.5)"


def test_aggregation_null_result_is_a_failure(context):
    outcome = _run(
        AggregationModule, context, table="orders", function="sum", column="amount",
        where="1 = 0", condition=">= 0",
    )  # fmt: skip
    assert outcome.status is CheckStatus.FAILURE
    assert "is NULL (no matching rows)" in outcome.message


def test_aggregation_compare_to_previous(context):
    params = dict(table="orders", function="count", period={"column": "created_at", "window": "1d"})
    ok = _run(
        AggregationModule, context, **params, compare_to_previous={"max_relative_change": 0.5}
    )
    assert ok.status is CheckStatus.SUCCESS
    assert ok.message == "count(*) 2 -> 3 (+50.0%, allowed ±50.0%)"
    assert ok.details["relative_change"] == pytest.approx(0.5)

    too_much = _run(
        AggregationModule, context, **params, compare_to_previous={"max_relative_change": 0.2}
    )
    assert too_much.status is CheckStatus.FAILURE


def test_aggregation_previous_period_zero(context):
    params = dict(
        table="orders",
        function="count",
        period={"column": "created_at", "window": "1h"},
        compare_to_previous={"max_relative_change": 0.5},
    )
    # [11:00, 12:00) has 1 order, [10:00, 11:00) has none.
    outcome = _run(AggregationModule, context, **params)
    assert outcome.status is CheckStatus.FAILURE
    assert "went from 0 to 1" in outcome.message
    both_empty = _run(AggregationModule, context, **{**params, "where": "1 = 0"})
    assert both_empty.status is CheckStatus.SUCCESS


# --- custom SQL -------------------------------------------------------------


def test_custom_sql_success_and_failure(context):
    ok = _run(CustomSqlModule, context, sql="SELECT COUNT(*) FROM orders", condition="== 6")
    assert ok.status is CheckStatus.SUCCESS
    assert ok.details == {"value": 6.0, "condition": "== 6"}
    bad = _run(CustomSqlModule, context, sql="SELECT COUNT(*) FROM orders", condition="< 5")
    assert bad.status is CheckStatus.FAILURE
    assert bad.message == "value 6, expected < 5"


def test_custom_sql_boolean_result(context):
    sql = "SELECT COUNT(*) = 6 FROM orders"
    assert _run(CustomSqlModule, context, sql=sql, condition="== 1").status is CheckStatus.SUCCESS


@pytest.mark.parametrize(
    ("sql", "status", "message"),
    [
        ("SELECT amount FROM orders WHERE 1 = 0", "failure", "query returned no rows"),
        ("SELECT NULL", "failure", "query returned NULL"),
        ("SELECT order_id FROM orders", "error", "exactly one row with one column, got 6 row(s)"),
        ("SELECT 1, 2", "error", "got 1 row(s) and 2 column(s)"),
        ("SELECT 'abc'", "error", "not numeric"),
    ],
)
def test_custom_sql_unexpected_results(context, sql, status, message):
    outcome = _run(CustomSqlModule, context, sql=sql, condition="> 0")
    assert outcome.status.value == status
    assert message in outcome.message


# --- helpers ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("delta", "text"),
    [
        (timedelta(seconds=0), "0s"),
        (timedelta(seconds=45), "45s"),
        (timedelta(minutes=90, seconds=5), "1h 30m 5s"),
        (timedelta(days=2, hours=3, seconds=9), "2d 3h"),
        (timedelta(minutes=-5), "-5m"),
    ],
)
def test_format_duration(delta, text):
    assert format_duration(delta) == text


def test_to_utc_datetime_handles_backend_types():
    expected = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    assert to_utc_datetime(datetime(2026, 3, 1, 10, 0)) == expected
    assert to_utc_datetime("2026-03-01 10:00:00") == expected
    assert to_utc_datetime("2026-03-01T10:00:00Z") == expected
    other_tz = datetime(2026, 3, 1, 7, 0, tzinfo=timezone(timedelta(hours=-3)))
    assert to_utc_datetime(other_tz) == expected
    with pytest.raises(TypeError):
        to_utc_datetime(42)


# --- same period logic through SQLAlchemy (SQLite stores timestamps as text) --


def test_period_and_freshness_work_on_sqlite(tmp_path):
    import sqlalchemy as sa

    from modular_data_ci.connections.sqlalchemy_source import SQLAlchemySource

    url = f"sqlite:///{tmp_path / 'shop.sqlite'}"
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE orders (order_id INTEGER, created_at TIMESTAMP)")
        conn.exec_driver_sql(
            "INSERT INTO orders VALUES (1, '2026-03-10 11:00:00'), (2, '2026-03-09 13:00:00'), "
            "(3, '2026-03-09 11:00:00')"
        )
    engine.dispose()
    source = SQLAlchemySource(url)
    context = ExecutionContext(source=source, now=NOW)
    try:
        count = _run(
            AggregationModule, context, table="orders", function="count",
            period={"column": "created_at", "window": "1d"}, condition="== 2",
        )  # fmt: skip
        assert count.status is CheckStatus.SUCCESS, count.message
        fresh = _run(
            FreshnessModule, context, table="orders", timestamp_column="created_at", max_age="2h"
        )
        assert fresh.status is CheckStatus.SUCCESS, fresh.message
    finally:
        source.close()

"""DuckDB fixtures for module tests."""

from datetime import datetime, timezone

import duckdb

from modular_data_ci.connections.duckdb_source import DuckDBSource
from modular_data_ci.modules import ExecutionContext

NOW = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def make_context(*statements: str) -> ExecutionContext:
    conn = duckdb.connect()
    for statement in statements:
        conn.execute(statement)
    return ExecutionContext(source=DuckDBSource.from_connection(conn), now=NOW)


def run_module(module_cls, context, **params):
    module = module_cls()
    return module.run(module.parse_params(params), context)

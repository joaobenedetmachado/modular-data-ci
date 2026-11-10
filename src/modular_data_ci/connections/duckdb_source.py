from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from modular_data_ci.connections.base import ColumnInfo, Parameters, split_identifier
from modular_data_ci.errors import DataSourceError


class DuckDBSource:
    dialect = "duckdb"

    def __init__(self, path: str = ":memory:", *, read_only: bool = False) -> None:
        # duckdb.connect() silently creates a new empty database for a missing file,
        # which would turn a wrong path into confusing "table not found" errors.
        if path != ":memory:" and not path.startswith("md:") and not Path(path).exists():
            raise DataSourceError(f"DuckDB database file not found: {path}")
        try:
            self._conn = duckdb.connect(path, read_only=read_only)
        except duckdb.Error as exc:
            raise DataSourceError(f"cannot open DuckDB database {path}: {exc}") from exc
        self.path = path

    @classmethod
    def from_connection(cls, connection: duckdb.DuckDBPyConnection) -> DuckDBSource:
        """Wrap an existing connection (useful in tests and notebooks)."""
        source = cls.__new__(cls)
        source._conn = connection
        source.path = "<connection>"
        return source

    def query(self, sql: str, parameters: Parameters | None = None) -> list[tuple[Any, ...]]:
        return self._conn.execute(sql, dict(parameters) if parameters else None).fetchall()

    def scalar(self, sql: str, parameters: Parameters | None = None) -> Any:
        row = self._conn.execute(sql, dict(parameters) if parameters else None).fetchone()
        return None if row is None else row[0]

    def columns(self, table: str) -> list[ColumnInfo]:
        parts = split_identifier(table)
        name = parts[-1]
        schema = parts[-2] if len(parts) >= 2 else None
        catalog = parts[-3] if len(parts) == 3 else None
        rows = self.query(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = $name
              AND table_schema = COALESCE($schema, current_schema())
              AND table_catalog = COALESCE($catalog, current_database())
            ORDER BY ordinal_position
            """,
            {"name": name, "schema": schema, "catalog": catalog},
        )
        if not rows:
            raise LookupError(f"table '{table}' not found")
        return [ColumnInfo(name=r[0], type=r[1], nullable=r[2] == "YES") for r in rows]

    def quote(self, identifier: str) -> str:
        return ".".join(
            '"' + part.replace('"', '""') + '"' for part in split_identifier(identifier)
        )

    def placeholder(self, name: str) -> str:
        return f"${name}"

    def close(self) -> None:
        self._conn.close()

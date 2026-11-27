from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from modular_data_ci.connections.base import ColumnInfo, Parameters, split_identifier
from modular_data_ci.errors import DataSourceError


class DuckDBSource:
    dialect = "duckdb"

    def __init__(
        self,
        path: str = ":memory:",
        *,
        read_only: bool = False,
        setup: tuple[str, ...] | list[str] = (),
        files: dict[str, str] | None = None,
    ) -> None:
        # duckdb.connect() silently creates a new empty database for a missing file,
        # which would turn a wrong path into confusing "table not found" errors.
        if path != ":memory:" and not path.startswith("md:") and not Path(path).exists():
            raise DataSourceError(f"DuckDB database file not found: {path}")
        try:
            self._conn = duckdb.connect(path, read_only=read_only)
        except duckdb.Error as exc:
            raise DataSourceError(f"cannot open DuckDB database {path}: {exc}") from exc
        self.path = path
        self._prepare(setup, files or {})

    def _prepare(self, setup: tuple[str, ...] | list[str], files: dict[str, str]) -> None:
        for index, statement in enumerate(setup):
            try:
                self._conn.execute(statement)
            except duckdb.Error as exc:
                self._conn.close()
                raise DataSourceError(f"connection.setup[{index}] failed: {exc}") from exc
        for view, file in files.items():
            if not any(ch in file for ch in "*?[") and not Path(file).exists():
                self._conn.close()
                raise DataSourceError(f"connection.files.{view}: file not found: {file}")
            literal = "'" + file.replace("'", "''") + "'"
            try:
                self._conn.execute(f'CREATE OR REPLACE VIEW "{view}" AS SELECT * FROM {literal}')
            except duckdb.Error as exc:
                self._conn.close()
                raise DataSourceError(
                    f"connection.files.{view}: cannot read {file}: {exc}"
                ) from exc

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

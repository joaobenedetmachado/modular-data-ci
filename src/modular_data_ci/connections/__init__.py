from __future__ import annotations

from typing import TYPE_CHECKING

from modular_data_ci.connections.base import ColumnInfo, DataSource, Parameters, split_identifier

if TYPE_CHECKING:
    from modular_data_ci.config.models import ConnectionConfig


def open_source(connection: ConnectionConfig) -> DataSource:
    """Open the data source described by the configuration."""
    from modular_data_ci.config.models import DuckDBConnection, SQLAlchemyConnection

    if isinstance(connection, DuckDBConnection):
        from modular_data_ci.connections.duckdb_source import DuckDBSource

        return DuckDBSource(connection.path, read_only=connection.read_only)
    if isinstance(connection, SQLAlchemyConnection):
        from modular_data_ci.connections.sqlalchemy_source import SQLAlchemySource

        return SQLAlchemySource(connection.url)
    raise TypeError(f"unsupported connection: {connection!r}")  # pragma: no cover


__all__ = ["ColumnInfo", "DataSource", "Parameters", "open_source", "split_identifier"]

"""Data source contract.

Modules never talk to DuckDB or SQLAlchemy directly. They receive a ``DataSource``
through the execution context, which keeps them testable and backend independent.

Because backends differ in parameter syntax and identifier quoting, modules build
SQL with ``quote()`` for table/column names and ``placeholder()`` for values::

    since = src.placeholder("since")
    sql = f"SELECT COUNT(*) FROM {src.quote(table)} WHERE {src.quote(col)} >= {since}"
    src.scalar(sql, {"since": since_value})
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

Parameters = Mapping[str, Any]


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    type: str
    """Backend type name as reported by the database, e.g. ``INTEGER``, ``VARCHAR``."""
    nullable: bool | None = None
    """Declared nullability; None when the backend does not report it."""


class DataSource(Protocol):
    dialect: str
    """Short backend name, e.g. ``duckdb``, ``postgresql``, ``sqlite``."""

    def query(self, sql: str, parameters: Parameters | None = None) -> list[tuple[Any, ...]]:
        """Run a query and return all rows."""
        ...

    def scalar(self, sql: str, parameters: Parameters | None = None) -> Any:
        """First column of the first row, or None when the query returns no rows."""
        ...

    def columns(self, table: str) -> list[ColumnInfo]:
        """Describe a table's columns. Raises ``LookupError`` if the table does not exist."""
        ...

    def quote(self, identifier: str) -> str:
        """Quote a (possibly dotted, e.g. ``schema.table``) identifier for this backend."""
        ...

    def placeholder(self, name: str) -> str:
        """Bind-parameter marker for ``name`` in this backend's syntax."""
        ...

    def close(self) -> None: ...


def split_identifier(identifier: str) -> list[str]:
    """Split ``catalog.schema.table`` into parts, rejecting empty parts."""
    parts = identifier.split(".")
    if not all(part.strip() for part in parts) or len(parts) > 3:
        raise ValueError(f"invalid table name {identifier!r}")
    return [part.strip() for part in parts]

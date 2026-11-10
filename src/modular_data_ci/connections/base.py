"""Data source contract.

Modules never talk to DuckDB or SQLAlchemy directly. They receive a ``DataSource``
through the execution context, which keeps them testable and backend independent.
Concrete DuckDB and SQLAlchemy implementations arrive with the engine (Day 3/4).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    type: str
    """Backend type name as reported by the database, e.g. ``INTEGER``, ``VARCHAR``."""
    nullable: bool | None = None
    """None when the backend does not report nullability."""


class DataSource(Protocol):
    def query(self, sql: str, parameters: Sequence[Any] | None = None) -> list[tuple[Any, ...]]:
        """Run a query and return all rows."""
        ...

    def scalar(self, sql: str, parameters: Sequence[Any] | None = None) -> Any:
        """Run a query that returns a single value (first column of the first row)."""
        ...

    def columns(self, table: str) -> list[ColumnInfo]:
        """Describe a table's columns. Raises ``LookupError`` if the table does not exist."""
        ...

    def close(self) -> None: ...

"""Test doubles shared across tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from modular_data_ci.connections import ColumnInfo, Parameters


class FakeSource:
    """In-memory DataSource. ``scalar`` returns ``value`` or calls ``handler(sql)``."""

    dialect = "fake"

    def __init__(self, value: Any = None, handler: Callable[[str], Any] | None = None) -> None:
        self.value = value
        self.handler = handler
        self.queries: list[str] = []
        self.closed = False

    def query(self, sql: str, parameters: Parameters | None = None) -> list[tuple[Any, ...]]:
        return [(self.scalar(sql, parameters),)]

    def scalar(self, sql: str, parameters: Parameters | None = None) -> Any:
        self.queries.append(sql)
        return self.handler(sql) if self.handler else self.value

    def columns(self, table: str) -> list[ColumnInfo]:
        return []

    def quote(self, identifier: str) -> str:
        return identifier

    def placeholder(self, name: str) -> str:
        return f":{name}"

    def close(self) -> None:
        self.closed = True

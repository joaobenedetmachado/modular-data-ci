from __future__ import annotations

from typing import Any

from modular_data_ci.connections.base import ColumnInfo, Parameters, split_identifier
from modular_data_ci.errors import DataSourceError

try:
    import sqlalchemy as sa
except ImportError:  # pragma: no cover - exercised only without the extra installed
    sa = None  # type: ignore[assignment]


class SQLAlchemySource:
    """Any database SQLAlchemy supports. Requires ``modular-data-ci[sqlalchemy]``.

    Uses one connection for the whole run; each statement runs in its own
    transaction so a failing query does not poison the following ones.
    """

    def __init__(self, url: str) -> None:
        if sa is None:
            raise DataSourceError(
                "the 'sqlalchemy' connection type needs SQLAlchemy: "
                "pip install 'modular-data-ci[sqlalchemy]'"
            )
        try:
            self._engine = sa.create_engine(url)
            self._conn = self._engine.connect()
        except Exception as exc:
            safe_url = _redact(url)
            raise DataSourceError(f"cannot connect to {safe_url}: {exc}") from exc
        self.dialect = self._engine.dialect.name

    def query(self, sql: str, parameters: Parameters | None = None) -> list[tuple[Any, ...]]:
        with self._conn.begin():
            result = self._conn.execute(sa.text(sql), dict(parameters or {}))
            return [tuple(row) for row in result]

    def scalar(self, sql: str, parameters: Parameters | None = None) -> Any:
        with self._conn.begin():
            row = self._conn.execute(sa.text(sql), dict(parameters or {})).first()
            return None if row is None else row[0]

    def columns(self, table: str) -> list[ColumnInfo]:
        parts = split_identifier(table)
        if len(parts) == 3:
            raise ValueError("catalog.schema.table names are not supported for SQLAlchemy")
        schema = parts[0] if len(parts) == 2 else None
        try:
            with self._conn.begin():
                raw = sa.inspect(self._conn).get_columns(parts[-1], schema=schema)
        except sa.exc.NoSuchTableError:
            raise LookupError(f"table '{table}' not found") from None
        if not raw:
            raise LookupError(f"table '{table}' not found")
        return [
            ColumnInfo(name=c["name"], type=str(c["type"]), nullable=c.get("nullable")) for c in raw
        ]

    def quote(self, identifier: str) -> str:
        preparer = self._engine.dialect.identifier_preparer
        return ".".join(preparer.quote(part) for part in split_identifier(identifier))

    def placeholder(self, name: str) -> str:
        return f":{name}"

    def close(self) -> None:
        self._conn.close()
        self._engine.dispose()


def _redact(url: str) -> str:
    try:
        return sa.engine.make_url(url).render_as_string(hide_password=True)
    except Exception:
        return "<database url>"

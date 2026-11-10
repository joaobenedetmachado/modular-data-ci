"""Small helpers shared by the built-in modules."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

from modular_data_ci.connections.base import DataSource


def where_clause(*conditions: str | None) -> str:
    parts = [f"({condition})" for condition in conditions if condition]
    return f" WHERE {' AND '.join(parts)}" if parts else ""


def timestamp_param(source: DataSource, value: datetime) -> Any:
    """Bind value for comparing with a timestamp column.

    Timestamp columns are assumed to hold UTC. The value is passed as a naive UTC
    datetime, or as ISO text for SQLite, which stores timestamps as text.
    """
    naive_utc = value.astimezone(timezone.utc).replace(tzinfo=None)
    if source.dialect == "sqlite":
        return naive_utc.isoformat(sep=" ")
    return naive_utc


def to_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    raise TypeError(f"expected a number, got {type(value).__name__}: {value!r}")


def to_utc_datetime(value: Any) -> datetime:
    """Convert a database timestamp to an aware UTC datetime. Naive values are UTC."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    elif isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, time.min)
    if not isinstance(value, datetime):
        raise TypeError(f"expected a timestamp, got {type(value).__name__}: {value!r}")
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def format_number(value: float) -> str:
    return f"{value:,.6g}" if abs(value) < 1e15 else f"{value:.6g}"


def format_duration(delta: timedelta) -> str:
    seconds = int(abs(delta.total_seconds()))
    sign = "-" if delta.total_seconds() < 0 else ""
    days, seconds = divmod(seconds, 86_400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = [f"{n}{unit}" for n, unit in ((days, "d"), (hours, "h"), (minutes, "m")) if n]
    if not parts or (seconds and not days):
        parts.append(f"{seconds}s")
    return sign + " ".join(parts)

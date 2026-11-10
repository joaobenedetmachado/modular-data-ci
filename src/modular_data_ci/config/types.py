"""Reusable field types for configuration models."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Annotated, Any

from pydantic import AfterValidator, BeforeValidator

_DURATION = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(s|m|h|d|w)\s*$")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86_400, "w": 604_800}


def parse_duration(value: Any) -> timedelta:
    """Parse ``"90s"``, ``"30m"``, ``"24h"``, ``"7d"``, ``"2w"`` or a number of seconds."""
    if isinstance(value, timedelta):
        return value
    if isinstance(value, bool):
        raise ValueError("duration must be a string like '24h' or a number of seconds")
    if isinstance(value, (int, float)):
        return timedelta(seconds=value)
    if isinstance(value, str):
        match = _DURATION.match(value)
        if match is None:
            raise ValueError(
                f"invalid duration {value!r}; use a number and a unit (s, m, h, d, w), e.g. '24h'"
            )
        return timedelta(seconds=float(match[1]) * _UNIT_SECONDS[match[2]])
    raise ValueError("duration must be a string like '24h' or a number of seconds")


def _require_positive(value: timedelta) -> timedelta:
    if value <= timedelta(0):
        raise ValueError("duration must be greater than zero")
    return value


Duration = Annotated[timedelta, BeforeValidator(parse_duration), AfterValidator(_require_positive)]

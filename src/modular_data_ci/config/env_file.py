"""Minimal ``.env`` reader for ``--env-file``.

Supports ``KEY=value``, ``export KEY=value``, comments, blank lines and single or
double quoted values. Variables already set in the environment win, so CI secrets
are never overridden by a committed file.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from modular_data_ci.errors import ConfigError

_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def read_env_file(path: str | Path) -> dict[str, str]:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(str(path), [f"cannot read env file: {exc.strerror or exc}"]) from None
    values: dict[str, str] = {}
    problems = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _LINE.match(line)
        if match is None:
            problems.append(f"line {number}: expected KEY=value")
            continue
        key, value = match[1], match[2]
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[key] = value
    if problems:
        raise ConfigError(str(path), problems)
    return values


def merged_env(base: Mapping[str, str], files: list[Path]) -> dict[str, str]:
    """Values from ``files`` (later files win) under the real environment."""
    merged: dict[str, str] = {}
    for path in files:
        merged.update(read_env_file(path))
    merged.update(base)
    return merged

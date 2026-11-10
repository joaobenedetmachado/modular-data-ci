"""Load a YAML configuration file into a validated :class:`Config`.

Steps, each with a readable :class:`ConfigError` on failure:

1. Read the file.
2. Parse YAML (duplicate keys are rejected instead of silently overwritten).
3. Interpolate environment variables in string values:
   ``${VAR}`` (must be set), ``${VAR:-default}`` (default when unset or empty),
   ``$${...}`` for a literal ``${...}``.
4. Validate with Pydantic and convert errors into one line per problem.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from modular_data_ci.config.models import Config
from modular_data_ci.errors import ConfigError

_REFERENCE = re.compile(r"\$(\$)?\{([^}]*)\}")
_VARIABLE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?::-(.*))?$", re.S)
_CONNECTION_TAGS = {"duckdb", "sqlalchemy"}


def load_config(path: str | Path, env: Mapping[str, str] | None = None) -> Config:
    path = Path(path)
    source = str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(source, ["file not found"]) from None
    except IsADirectoryError:
        raise ConfigError(source, ["expected a file, got a directory"]) from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(source, [f"cannot read file: {exc}"]) from None
    return parse_config(text, env=env, source=source)


def parse_config(
    text: str, *, env: Mapping[str, str] | None = None, source: str = "<string>"
) -> Config:
    raw = _parse_yaml(text, source)
    raw = interpolate_env(raw, os.environ if env is None else env, source=source)
    try:
        return Config.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(source, format_validation_error(exc, raw)) from None


# --- YAML -------------------------------------------------------------------


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys."""


def _construct_mapping(loader: _StrictLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", key_node.start_mark
            )
        mapping[key] = loader.construct_object(value_node)
    return mapping


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def _parse_yaml(text: str, source: str) -> dict[str, Any]:
    try:
        data = yaml.load(text, Loader=_StrictLoader)  # safe: _StrictLoader extends SafeLoader
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark or exc.context_mark
        where = f"line {mark.line + 1}, column {mark.column + 1}: " if mark else ""
        problem = exc.problem or exc.context or "invalid YAML"
        raise ConfigError(source, [f"YAML syntax error at {where}{problem}"]) from None
    except yaml.YAMLError as exc:
        raise ConfigError(source, [f"YAML error: {exc}"]) from None
    if data is None:
        raise ConfigError(source, ["file is empty"])
    if not isinstance(data, dict):
        raise ConfigError(source, [f"top level must be a mapping, got {type(data).__name__}"])
    return data


# --- environment variables --------------------------------------------------


def interpolate_env(data: Any, env: Mapping[str, str], *, source: str = "<string>") -> Any:
    """Replace ``${VAR}`` references in every string value (keys are left as-is)."""
    problems: list[str] = []
    result = _interpolate(data, env, "", problems)
    if problems:
        raise ConfigError(source, problems)
    return result


def _interpolate(value: Any, env: Mapping[str, str], path: str, problems: list[str]) -> Any:
    if isinstance(value, str):
        return _interpolate_string(value, env, path, problems)
    if isinstance(value, dict):
        return {
            key: _interpolate(item, env, _join(path, str(key)), problems)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _interpolate(item, env, f"{path}[{index}]", problems)
            for index, item in enumerate(value)
        ]
    return value


def _interpolate_string(text: str, env: Mapping[str, str], path: str, problems: list[str]) -> str:
    def replace(match: re.Match[str]) -> str:
        escaped, inner = match[1], match[2]
        if escaped:
            return "${" + inner + "}"
        variable = _VARIABLE.match(inner)
        if variable is None:
            problems.append(f"{path}: invalid variable reference '${{{inner}}}'")
            return match[0]
        name, default = variable[1], variable[2]
        current = env.get(name)
        if default is not None:
            return current if current else default
        if current is None:
            problems.append(
                f"{path}: environment variable {name} is not set "
                f"(use ${{{name}:-default}} to make it optional)"
            )
            return match[0]
        return current

    return _REFERENCE.sub(replace, text)


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


# --- validation errors ------------------------------------------------------


def format_validation_error(exc: ValidationError, raw: Any, *, prefix: str = "") -> list[str]:
    """One readable line per Pydantic error, with check names instead of bare indexes.

    ``prefix`` is prepended to every location, e.g. ``checks[2] (orders_fresh)``.
    """
    lines = []
    for error in exc.errors(include_url=False):
        location = _format_location(error["loc"], raw)
        if prefix:
            location = f"{prefix}.{location}" if location else prefix
        message = _format_message(error)
        lines.append(f"{location}: {message}" if location else message)
    return lines


def _format_location(loc: tuple[Any, ...], raw: Any) -> str:
    parts: list[str] = []
    node = raw
    for index, part in enumerate(loc):
        # Drop the union tag Pydantic inserts for discriminated unions: connection.duckdb.path
        if index == 1 and loc[0] == "connection" and part in _CONNECTION_TAGS:
            continue
        # Pydantic adds the validator/branch name for some nested errors; skip non-path parts.
        if isinstance(part, str) and part.startswith(("function-", "tagged-union")):
            continue
        if isinstance(part, int):
            label = f"[{part}]"
            if isinstance(node, list) and part < len(node):
                node = node[part]
                if loc[0] == "checks" and index == 1 and isinstance(node, dict):
                    name = node.get("name")
                    if isinstance(name, str) and name:
                        label += f" ({name})"
            else:
                node = None
            parts.append(label)
        else:
            node = node.get(part) if isinstance(node, dict) else None
            parts.append(f".{part}" if parts else str(part))
    return "".join(parts)


def _format_message(error: Any) -> str:
    kind = error["type"]
    if kind == "missing":
        return "required field is missing"
    if kind == "extra_forbidden":
        return "unknown key"
    if kind == "union_tag_invalid":
        ctx = error.get("ctx", {})
        return f"unknown type {ctx.get('tag')!r}; expected one of {ctx.get('expected_tags')}"
    message = str(error["msg"])
    for prefix in ("Value error, ", "Assertion failed, "):
        if message.startswith(prefix):
            return message[len(prefix) :]
    return message

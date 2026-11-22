"""Pattern module: string values fully match a regular expression."""

from __future__ import annotations

import re

from pydantic import Field, field_validator

from modular_data_ci.connections.base import DataSource
from modular_data_ci.modules._sql import where_clause
from modular_data_ci.modules.base import ExecutionContext, ModuleParams, ValidationModule
from modular_data_ci.results import CheckOutcome

# Dialects that can evaluate the regex in SQL. Others fall back to Python.
_SQL_MATCH = {
    "duckdb": "regexp_full_match({column}, {pattern})",
    "postgresql": "{column} ~ {pattern}",
    "mysql": "{column} REGEXP {pattern}",
    "mariadb": "{column} REGEXP {pattern}",
}
_ANCHORED = {"postgresql", "mysql", "mariadb"}  # partial-match operators need ^...$


class PatternParams(ModuleParams):
    table: str = Field(min_length=1)
    column: str = Field(min_length=1)
    regex: str = Field(min_length=1)
    """Each non-NULL value must match the whole expression."""
    where: str | None = None
    sample_size: int = Field(default=5, ge=0, le=100)

    @field_validator("regex")
    @classmethod
    def _compiles(cls, value: str) -> str:
        try:
            re.compile(value)
        except re.error as exc:
            raise ValueError(f"invalid regular expression: {exc}") from None
        return value


class PatternModule(ValidationModule[PatternParams]):
    name = "pattern"
    params_model = PatternParams

    def run(self, params: PatternParams, context: ExecutionContext) -> CheckOutcome:
        source = context.source
        if source.dialect in _SQL_MATCH:
            invalid, sample = self._in_sql(source, params)
        else:
            invalid, sample = self._in_python(source, params)
        details: dict[str, object] = {
            "table": params.table,
            "column": params.column,
            "regex": params.regex,
            "invalid_rows": invalid,
        }
        if not invalid:
            return CheckOutcome.success(f"all {params.column} values match", **details)
        if sample:
            details["sample"] = sample
        return CheckOutcome.failure(
            f"{invalid} row(s) where {params.column} does not match /{params.regex}/", **details
        )

    def _in_sql(self, source: DataSource, params: PatternParams) -> tuple[int, list[str]]:
        column = source.quote(params.column)
        regex = f"^(?:{params.regex})$" if source.dialect in _ANCHORED else params.regex
        match = _SQL_MATCH[source.dialect].format(
            column=column, pattern=source.placeholder("pattern")
        )
        condition = f"{column} IS NOT NULL AND NOT ({match})"
        base = f"FROM {source.quote(params.table)}{where_clause(params.where, condition)}"
        bind = {"pattern": regex}
        invalid = int(source.scalar(f"SELECT COUNT(*) {base}", bind) or 0)
        sample: list[str] = []
        if invalid and params.sample_size:
            rows = source.query(
                f"SELECT DISTINCT {column} {base} ORDER BY 1 LIMIT {params.sample_size}", bind
            )
            sample = [str(row[0]) for row in rows]
        return invalid, sample

    def _in_python(self, source: DataSource, params: PatternParams) -> tuple[int, list[str]]:
        column = source.quote(params.column)
        rows = source.query(
            f"SELECT {column}, COUNT(*) FROM {source.quote(params.table)}"
            f"{where_clause(params.where, f'{column} IS NOT NULL')} GROUP BY {column}"
        )
        compiled = re.compile(params.regex)
        bad = sorted(
            (str(value), int(count)) for value, count in rows if not compiled.fullmatch(str(value))
        )
        return sum(count for _, count in bad), [value for value, _ in bad[: params.sample_size]]

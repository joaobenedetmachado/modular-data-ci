"""Schema module: columns exist, have the expected types, and required ones have no NULLs."""

from __future__ import annotations

from pydantic import Field

from modular_data_ci.modules.base import ExecutionContext, ModuleParams, ValidationModule
from modular_data_ci.results import CheckOutcome


class ColumnSpec(ModuleParams):
    type: str | None = None
    """Expected backend type (case-insensitive), e.g. ``integer``. None skips the type check."""
    required: bool = True
    """The column must exist in the table."""
    nullable: bool = True
    """When False, the column must not contain NULL values."""


class SchemaParams(ModuleParams):
    table: str = Field(min_length=1)
    columns: dict[str, ColumnSpec] = Field(min_length=1)
    allow_extra_columns: bool = True
    """When False, columns not listed in ``columns`` cause a failure."""


# Synonyms reported or accepted by common backends, mapped to one canonical name.
_TYPE_ALIASES = {
    "INT": "INTEGER",
    "INT4": "INTEGER",
    "INT32": "INTEGER",
    "SIGNED": "INTEGER",
    "INT8": "BIGINT",
    "INT64": "BIGINT",
    "LONG": "BIGINT",
    "INT2": "SMALLINT",
    "SHORT": "SMALLINT",
    "FLOAT8": "DOUBLE",
    "FLOAT64": "DOUBLE",
    "DOUBLE PRECISION": "DOUBLE",
    "FLOAT4": "REAL",
    "STRING": "VARCHAR",
    "TEXT": "VARCHAR",
    "CHARACTER VARYING": "VARCHAR",
    "BOOL": "BOOLEAN",
    "LOGICAL": "BOOLEAN",
    "DATETIME": "TIMESTAMP",
    "TIMESTAMP WITHOUT TIME ZONE": "TIMESTAMP",
    "TIMESTAMP WITH TIME ZONE": "TIMESTAMPTZ",
    "NUMERIC": "DECIMAL",
}


def normalize_type(type_name: str) -> str:
    text = " ".join(type_name.upper().split())
    base, paren, rest = text.partition("(")
    base = _TYPE_ALIASES.get(base.strip(), base.strip())
    return f"{base}({rest.replace(' ', '')}" if paren else base


def types_match(expected: str, actual: str) -> bool:
    """``integer`` matches ``INT4``; ``varchar`` matches ``VARCHAR(255)``;
    ``decimal(18,2)`` only matches that exact precision and scale."""
    wanted, found = normalize_type(expected), normalize_type(actual)
    if "(" in wanted:
        return wanted == found
    return found.partition("(")[0] == wanted


class SchemaModule(ValidationModule[SchemaParams]):
    name = "schema"
    params_model = SchemaParams

    def run(self, params: SchemaParams, context: ExecutionContext) -> CheckOutcome:
        source = context.source
        try:
            actual = source.columns(params.table)
        except LookupError as exc:
            return CheckOutcome.failure(str(exc), table=params.table)

        by_name = {column.name.lower(): column for column in actual}
        problems: list[str] = []
        null_counts: dict[str, int] = {}

        for name, spec in params.columns.items():
            column = by_name.get(name.lower())
            if column is None:
                if spec.required:
                    problems.append(f"missing column '{name}'")
                continue
            if spec.type is not None and not types_match(spec.type, column.type):
                problems.append(f"column '{name}' is {column.type}, expected {spec.type}")
            if not spec.nullable:
                nulls = source.scalar(
                    f"SELECT COUNT(*) FROM {source.quote(params.table)} "
                    f"WHERE {source.quote(column.name)} IS NULL"
                )
                null_counts[name] = int(nulls or 0)
                if nulls:
                    problems.append(f"column '{name}' has {nulls} NULL value(s)")

        if not params.allow_extra_columns:
            expected = {name.lower() for name in params.columns}
            extra = [column.name for column in actual if column.name.lower() not in expected]
            if extra:
                problems.append(f"unexpected column(s): {', '.join(extra)}")

        details = {
            "table": params.table,
            "problems": problems,
            "actual_columns": {column.name: column.type for column in actual},
            "null_counts": null_counts,
        }
        if problems:
            return CheckOutcome.failure(
                f"{len(problems)} schema problem(s): {'; '.join(problems)}", **details
            )
        return CheckOutcome.success(
            f"{len(params.columns)} column(s) match in {params.table}", **details
        )

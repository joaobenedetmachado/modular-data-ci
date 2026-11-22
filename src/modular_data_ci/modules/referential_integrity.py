"""Referential integrity module: every foreign key value exists in the referenced table."""

from __future__ import annotations

from pydantic import Field

from modular_data_ci.modules._sql import where_clause
from modular_data_ci.modules.base import ExecutionContext, ModuleParams, ValidationModule
from modular_data_ci.results import CheckOutcome


class Reference(ModuleParams):
    table: str = Field(min_length=1)
    column: str = Field(min_length=1)


class ReferentialIntegrityParams(ModuleParams):
    table: str = Field(min_length=1)
    column: str = Field(min_length=1)
    references: Reference
    where: str | None = None
    """Filter on the child table."""
    sample_size: int = Field(default=5, ge=0, le=100)


class ReferentialIntegrityModule(ValidationModule[ReferentialIntegrityParams]):
    name = "referential_integrity"
    params_model = ReferentialIntegrityParams

    def run(self, params: ReferentialIntegrityParams, context: ExecutionContext) -> CheckOutcome:
        source = context.source
        child_column = f"c.{source.quote(params.column)}"
        parent_column = f"p.{source.quote(params.references.column)}"
        orphan = (
            f"{child_column} IS NOT NULL AND NOT EXISTS (SELECT 1 FROM "
            f"{source.quote(params.references.table)} p WHERE {parent_column} = {child_column})"
        )
        base = f"FROM {source.quote(params.table)} c{where_clause(params.where, orphan)}"
        orphans = int(source.scalar(f"SELECT COUNT(*) {base}") or 0)
        target = f"{params.references.table}.{params.references.column}"
        details: dict[str, object] = {
            "table": params.table,
            "column": params.column,
            "references": target,
            "orphan_rows": orphans,
        }
        if not orphans:
            return CheckOutcome.success(f"every {params.column} exists in {target}", **details)
        if params.sample_size:
            rows = source.query(
                f"SELECT DISTINCT {child_column} {base} ORDER BY 1 LIMIT {params.sample_size}"
            )
            details["sample"] = [row[0] for row in rows]
        return CheckOutcome.failure(
            f"{orphans} row(s) in {params.table} with {params.column} missing from {target}",
            **details,
        )

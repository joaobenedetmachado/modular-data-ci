"""Starter configuration written by ``modular-data-ci init``."""

from __future__ import annotations

STARTER_CONFIG = """\
# Modular Data CI configuration. Reference:
# https://github.com/joaobenedetmachado/modular-data-ci/blob/main/docs/configuration.md

version: 1

connection:
  type: {connection_type}
{connection_body}

checks:
  - name: {table}_not_empty
    module: row_count
    table: {table}
    min: 1

  - name: {table}_ids_unique
    module: uniqueness
    table: {table}
    columns: [id]

  - name: {table}_fresh
    module: freshness
    table: {table}
    timestamp_column: updated_at
    max_age: 24h
    required: false   # warning only until you confirm the column name
"""


def starter_config(*, connection_type: str = "duckdb", table: str = "my_table") -> str:
    if connection_type == "duckdb":
        body = "  path: ${MDCI_DUCKDB_PATH:-data/warehouse.duckdb}"
    elif connection_type == "sqlalchemy":
        body = "  url: ${DATABASE_URL}"
    else:
        raise ValueError(f"unknown connection type {connection_type!r}")
    return STARTER_CONFIG.format(connection_type=connection_type, connection_body=body, table=table)

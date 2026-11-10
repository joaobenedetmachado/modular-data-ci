# modular-data-ci

[![CI](https://github.com/joaobenedetmachado/modular-data-ci/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/joaobenedetmachado/modular-data-ci/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.12%20%7C%203.14-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/status-pre--alpha-orange)](PROJECT_PLAN.md)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![DuckDB](https://img.shields.io/badge/DuckDB-FFF000?logo=duckdb&logoColor=black)](https://duckdb.org)
[![Pydantic v2](https://img.shields.io/badge/pydantic-v2-E92063?logo=pydantic&logoColor=white)](https://docs.pydantic.dev)

Configuration-driven data quality checks for CI. Define reusable checks in YAML, run them locally with a CLI, and run the exact same checks in GitHub Actions.

> **Status:** early development, working toward **v0.1.0**. The engine and the four modules work; the `run` command and the GitHub Actions integration are next, and the package is not on PyPI yet. Progress is tracked in [PROJECT_PLAN.md](PROJECT_PLAN.md).

## Why

Data pipelines break quietly: a column changes type, a table stops updating, a daily total drifts. Modular Data CI makes those checks part of your CI, so a pull request fails when the data it depends on no longer meets the rules you defined.

It is focused on validation. It is not an orchestrator, a cloud service, or a dashboard.

## How it works

```
YAML config ──> Configuration Layer ──> Module Registry ──> Execution Engine ──> Reporting
                (Pydantic validation)    (resolve modules)   (run, collect)      (terminal + JSON)
```

The CLI and the GitHub Actions integration share one execution engine, so local runs and CI runs behave the same.

## Modules

| Module | What it checks |
|---|---|
| `schema` | Columns, types, required fields, structural consistency |
| `aggregation` | Aggregates over configurable periods, compared with operators, expected values and tolerances |
| `freshness` | The dataset was updated within an expected time window |
| `custom_sql` | User-defined SQL whose result is evaluated against a condition |

## Planned usage

Example config (`modular-data-ci.yml`):

```yaml
connection:
  type: duckdb
  path: data/warehouse.duckdb

checks:
  - name: orders_schema
    module: schema
    table: orders
    columns:
      order_id: { type: integer, nullable: false }
      amount: { type: double, nullable: false }
      created_at: { type: timestamp }

  - name: orders_fresh
    module: freshness
    table: orders
    timestamp_column: created_at
    max_age: 24h

  - name: daily_revenue_positive
    module: custom_sql
    sql: SELECT SUM(amount) FROM orders WHERE created_at >= CURRENT_DATE
    condition: "> 0"

  - name: daily_orders_stable
    module: aggregation
    required: false          # reported, but does not fail CI
    table: orders
    function: count
    period: { column: created_at, window: 1d }
    compare_to_previous: { max_relative_change: 0.3 }
```

Every check accepts `name`, `module`, `enabled` (default `true`), `required` (default `true`), `description` and `when`. All other keys belong to the module.

Checks can run conditionally, and any value can come from the environment:

```yaml
connection:
  type: sqlalchemy
  url: ${DATABASE_URL}              # secrets stay out of the file

modules:
  aggregation:
    enabled: ${RUN_AGGREGATIONS:-true}

checks:
  - name: orders_fresh
    module: freshness
    table: orders
    timestamp_column: created_at
    max_age: 24h
    when:
      env: { GITHUB_REF_NAME: main }   # only on main
      depends_on: orders_schema        # only if the schema check passed
      sql: SELECT COUNT(*) > 0 FROM orders
```

Full reference: [docs/configuration.md](docs/configuration.md). Complete example: [examples/modular-data-ci.yml](examples/modular-data-ci.yml).

Run locally:

```bash
pip install modular-data-ci
modular-data-ci run --config modular-data-ci.yml --report report.json
```

The command prints a readable summary, writes a JSON report, and exits non-zero when a required check fails, which is what makes CI fail.

In GitHub Actions:

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: "3.12"
- run: pip install modular-data-ci
- run: modular-data-ci run --config modular-data-ci.yml --report report.json
```

## Result statuses

Every check returns one of: `success`, `failure`, `skipped`, `error`. A run fails (exit code `1`) when a required check ends in `failure` or `error`. Exit code `2` means the configuration or arguments are invalid.

See [docs/architecture.md](docs/architecture.md) for the layers and module contract.

## Development

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .

# sample database for examples/modular-data-ci.yml (add --broken to see failures)
uv run python examples/make_sample_db.py
```

## Tech stack

Python, YAML + Pydantic, DuckDB, SQLAlchemy, Pytest, Ruff, GitHub Actions.

## Roadmap

See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the 7-day MVP plan, scope boundaries and future ideas (more modules, Airflow and Databricks integrations).

## License

[MIT](LICENSE)

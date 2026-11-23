# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-23

First public release.

### Added

- YAML configuration validated with Pydantic, with readable error locations, environment variable interpolation (`${VAR}`, `${VAR:-default}`) and duplicate-key detection.
- `when` execution conditions: `env`, `depends_on` and `sql`.
- Module registry with entry-point plugins (`modular_data_ci.modules`).
- Execution engine that never stops on a single broken check and always produces a report.
- DuckDB and SQLAlchemy data sources.
- Built-in modules: `schema`, `aggregation`, `freshness`, `custom_sql`.
- CLI: `run`, `validate`, `list`, `modules`; `--only`, `--skip`, `--module`, `-v`, `-q`, `--color`.
- Reports: terminal summary, JSON (`schema_version` 1), JUnit XML, GitHub annotations and job summary.
- Composite GitHub Action with `passed` output.

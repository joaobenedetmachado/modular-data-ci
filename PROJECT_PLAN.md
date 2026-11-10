# Modular Data CI

Technical Project Scope & 7-Day MVP Execution Plan
**Target:** v0.1.0

> Use this checklist as the single project tracking note. Mark each task as it is completed and keep the MVP scope controlled.

## Project Overview

Modular Data CI is a configuration-driven framework for data quality validation in Continuous Integration workflows. Developers and data engineers define reusable checks in YAML and execute them consistently through a local CLI or GitHub Actions.

The CLI and CI integration must use the same execution engine. The goal is focused data validation, not building another general-purpose orchestrator.

## Core Architecture

1. **Configuration Layer:** parse and validate YAML configuration, module settings, parameters, and execution conditions.
2. **Module Registry:** register and resolve available validation modules through a standardized interface.
3. **Execution Engine:** run enabled checks, handle errors, and collect results.
4. **Validation Modules:** independent components implementing specific data quality checks.
5. **Reporting Layer:** produce readable terminal output and machine-readable JSON reports.

## Initial Modules

- **Schema:** validate columns, types, required fields, and structural consistency.
- **Aggregation:** compare calculated aggregates across configurable periods, operators, expected values, and tolerances.
- **Freshness:** verify that datasets were updated within an expected time interval.
- **Custom SQL:** execute user-defined SQL checks and evaluate their results against configured conditions.

## Technology Direction

- Python; YAML + Pydantic; DuckDB for local analytical/testing workflows.
- SQLAlchemy for database connectivity where appropriate.
- Pytest for tests; Ruff for linting.
- GitHub Actions for CI integration; JSON for structured reports.

## 7-Day Delivery Checklist

### Day 1: Foundation & Architecture

- [x] Create repository and Python project structure.
- [x] Define module contracts and standardized result models.
- [x] Define and implement Pydantic configuration schemas.
- [x] Configure test and lint tooling.

**Deliverable:** runnable project skeleton and documented architecture.

### Day 2: Configuration Engine

- [ ] Implement YAML loading and parsing.
- [ ] Validate configuration schema and invalid settings.
- [ ] Support enabling and disabling modules.
- [ ] Define optional execution conditions.
- [ ] Add configuration tests and sample YAML.

**Deliverable:** validated configuration ready for execution.

### Day 3: Modular Execution Engine

- [ ] Implement the base validation module interface.
- [ ] Build the module registry.
- [ ] Implement module resolution and execution.
- [ ] Standardize success, failure, skipped, and error results.
- [ ] Add execution and error-handling tests.

**Deliverable:** engine capable of executing registered modules.

### Day 4: Core Validation Modules

- [ ] Implement schema validation.
- [ ] Implement aggregation validation, including configurable periods and tolerances.
- [ ] Implement freshness validation.
- [ ] Implement custom SQL validation.
- [ ] Create sample datasets and module-level tests.

**Deliverable:** four working validation modules.

### Day 5: CLI & Reporting

- [ ] Implement the `modular-data-ci run` command.
- [ ] Support configuration file arguments.
- [ ] Add readable terminal output.
- [ ] Generate structured JSON reports.
- [ ] Return non-zero exit codes when required checks fail.
- [ ] Test local execution end to end.

**Deliverable:** complete local CLI workflow.

### Day 6: GitHub Actions Integration

- [ ] Create a GitHub Actions workflow or reusable integration.
- [ ] Execute configured checks in a GitHub-hosted runner.
- [ ] Verify workflow failure when data quality requirements fail.
- [ ] Test successful and failing runs in a sample repository.
- [ ] Document CI setup and usage.

**Deliverable:** working automated data validation in GitHub Actions.

### Day 7: Hardening, Documentation & Release

- [ ] Run end-to-end tests.
- [ ] Fix remaining bugs and edge cases.
- [ ] Review architecture and module extensibility.
- [ ] Complete README and configuration reference.
- [ ] Add practical examples and sample workflows.
- [ ] Prepare v0.1.0 release.

**Deliverable:** functional, documented MVP ready for public use.

## Definition of Done

1. A developer can install the framework.
2. Define data quality checks in YAML.
3. Run checks locally through the CLI.
4. Run the same checks automatically through GitHub Actions.
5. Receive standardized reports with statuses and failure details.
6. Automatically fail CI when configured data quality requirements are not met.

## Scope Boundaries

Keep the first release focused on reliable validation and CI integration. Do not expand the MVP into a distributed processing platform, cloud service, web dashboard, or full pipeline orchestrator.

## Future Possibilities

- Additional validation modules.
- Integrations with Apache Airflow and other orchestrators.
- Native Databricks and broader data-platform integrations.
- More advanced conditions and reusable module packages.

## Development Principles

- Configuration-driven, but explicit and predictable.
- Modular contracts with minimal coupling.
- Same behavior locally and in CI.
- Useful error messages and reproducible results.
- Tests for core execution paths before release.

## Final Objective

Deliver Modular Data CI v0.1.0 in seven days: a small, reliable, extensible framework that makes data quality validation a first-class part of CI workflows.

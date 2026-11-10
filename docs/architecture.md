# Architecture

Modular Data CI turns a YAML file into a list of data quality checks, runs them against a data source, and reports the results. The CLI and the GitHub Actions integration call the same engine, so a run behaves the same locally and in CI.

## Flow

```
modular-data-ci.yml
        │
        ▼
┌───────────────────────┐   shape of the file: connection, check names, flags
│  Configuration layer  │   (config/models.py, Pydantic)
└───────────┬───────────┘
            ▼
┌───────────────────────┐   module name ──> module class
│    Module registry    │   module params validated by the module's params_model
└───────────┬───────────┘
            ▼
┌───────────────────────┐   skip disabled checks, time each check,
│   Execution engine    │   turn exceptions into `error`, collect results
└───────────┬───────────┘
            ▼
┌───────────────────────┐   schema · aggregation · freshness · custom_sql
│  Validation modules   │   talk to data only through the DataSource protocol
└───────────┬───────────┘
            ▼
┌───────────────────────┐   terminal summary + JSON report (RunReport)
│    Reporting layer    │   exit code from RunReport.passed
└───────────────────────┘
```

## Package layout

| Path | Responsibility | Status |
|---|---|---|
| `config/models.py` | Top-level `Config`, `CheckConfig`, `ModuleSettings`, connection configs | Day 1 / Day 2 |
| `config/loader.py` | YAML loading, env interpolation, readable errors | Day 2 |
| `config/when.py` | `when` conditions (env, depends_on, sql) and their evaluation | Day 2 |
| `config/selection.py` | Which checks take part in a run (filters, enabled flags) | Day 2 |
| `config/types.py` | Shared field types (`Duration`) | Day 1 |
| `conditions.py` | `Condition` and `Tolerance`, shared numeric comparisons | Day 1 |
| `results.py` | `CheckStatus`, `CheckOutcome`, `CheckResult`, `RunReport`, exit codes | Day 1 |
| `errors.py` | `ConfigError`, `SelectionError` (shown without traceback) | Day 2 |
| `connections/base.py` | `DataSource` protocol (`query`, `scalar`, `columns`, `quote`, `placeholder`), `ColumnInfo` | Day 1 / Day 3 |
| `connections/duckdb_source.py` | DuckDB data source | Day 3 |
| `connections/sqlalchemy_source.py` | SQLAlchemy data source (optional extra) | Day 3 |
| `registry.py` | `ModuleRegistry` (built-ins, entry-point plugins), `resolve_checks` | Day 3 |
| `engine.py` | `Engine.run()`: resolve, plan, open source, run in order, build `RunReport` | Day 3 |
| `modules/base.py` | `ValidationModule`, `ModuleParams`, `ExecutionContext` | Day 1 |
| `modules/<name>.py` | Params models now, module classes on Day 4 | Day 1 / Day 4 |
| `cli.py` | Entry point (`--version` today, `run` on Day 5) | Day 1 / Day 5 |

## Contracts

### Configuration is validated in two stages

1. `Config` validates what every check has in common: `name` (unique, `[A-Za-z0-9_.-]`), `module`, `enabled`, `required`, `description`, plus the `connection`. Unknown top-level keys are rejected.
2. Every other key on a check is kept in `CheckConfig.params` and validated by the module's own `params_model`. Module params reject unknown keys, so typos such as `nulable` fail loudly.

This split is what keeps modules decoupled: adding a module never changes the config layer.

### Validation module

```python
class ValidationModule(ABC, Generic[ParamsT]):
    name: ClassVar[str]  # used in YAML: `module: <name>`
    params_model: ClassVar[type[ModuleParams]]  # module-specific settings

    def run(self, params: ParamsT, context: ExecutionContext) -> CheckOutcome: ...
```

A module only decides whether the data meets the expectation and explains why. It does not handle timing, `enabled`/`required`, or unexpected exceptions; the engine does. `ExecutionContext` carries the `DataSource` and a fixed reference time `now`, so time-based checks are reproducible and testable.

### Data source

Modules access data only through the `DataSource` protocol (`query`, `scalar`, `columns`, `quote`, `placeholder`, `close`). DuckDB and SQLAlchemy implementations plug in behind it, and tests use a fake. Backends differ in bind-parameter syntax (`$name` vs `:name`) and identifier quoting, so modules build SQL with `quote()` for names and `placeholder()` for values instead of hard-coding either.

### Results

| Status | Meaning |
|---|---|
| `success` | The data met the expectation |
| `failure` | The check ran and the data did not meet the expectation |
| `skipped` | Not run (disabled, or its condition was not met) |
| `error` | Could not complete (bad SQL, missing table, exception) |

A result is **blocking** when the check is `required` and its status is `failure` or `error`. A run passes when no result is blocking.

| Exit code | Meaning |
|---|---|
| `0` | All required checks passed |
| `1` | At least one required check failed or errored |
| `2` | Invalid arguments or configuration; nothing was run |

### Conditions

Aggregation and custom SQL compare a number with a `Condition`: an operator (`==`, `!=`, `>`, `>=`, `<`, `<=`), a value, and an optional tolerance (`absolute` and/or `relative`; the larger allowance wins). The shorthand `"> 0"` is accepted. A missing value (`NULL`, NaN) never satisfies a condition.

## Design decisions

- **Two-stage validation** keeps the config layer stable while modules evolve.
- **Strict models** (`extra="forbid"`) everywhere except `CheckConfig`, whose extras are the module params and are validated strictly in stage 2.
- **Injected clock** (`ExecutionContext.now`) instead of calling `datetime.now()` inside modules.
- **`required: false`** lets teams add warning-only checks without breaking CI.
- **Few dependencies:** pydantic, pyyaml and duckdb are core; SQLAlchemy is an optional extra (`pip install modular-data-ci[sqlalchemy]`).

## Engine guarantees

- Every check is resolved (module found, params valid) before anything runs, including disabled checks. Problems raise `ConfigError` (exit code 2) and the data source is never opened.
- The data source is opened only if at least one check will run, and is always closed.
- Checks run in file order. A failing, erroring or raising check never stops the run.
- If the data source cannot be opened, every check that would run is reported as `error`, so the JSON report is still produced.
- Module `details` are converted to JSON-safe values (datetimes to ISO strings, `Decimal` to strings, unknown objects to `str`).
- Every check in a run sees the same reference time (`ExecutionContext.now`).

## Plugins

Third-party packages can add modules without changes to this repository:

```toml
[project.entry-points."modular_data_ci.modules"]
row_count = "my_package.checks:RowCountModule"
```

The entry point name must equal the module's `name`. Name clashes with built-in modules are rejected.

## Open items for the next days

- Day 4: the four built-in modules, registered in `registry._builtin_modules()`.
- Day 5: CLI `run` wiring `--only`, `--skip`, `--module`, terminal and JSON reporters.

Full configuration reference: [configuration.md](configuration.md).

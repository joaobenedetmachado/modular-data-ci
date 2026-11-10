# Configuration reference

A configuration file is YAML. A complete example lives in [`examples/modular-data-ci.yml`](../examples/modular-data-ci.yml).

```yaml
version: 1            # optional, only 1 is supported
connection: { ... }   # required
modules: { ... }      # optional
checks: [ ... ]       # required, at least one
```

Unknown keys are rejected everywhere, so typos fail loudly instead of being ignored. Duplicate keys in a mapping are also rejected.

## `connection`

| Type | Keys |
|---|---|
| `duckdb` | `path` (default `:memory:`), `read_only` (default `false`). Relative paths are relative to the working directory. A missing file is an error (DuckDB would otherwise create an empty database) |
| `sqlalchemy` | `url` (required). Needs `pip install modular-data-ci[sqlalchemy]` plus the database driver. Passwords are hidden in connection error messages |

```yaml
connection:
  type: sqlalchemy
  url: ${DATABASE_URL}
```

## `modules`

Settings applied to every check of a module. Today only `enabled`:

```yaml
modules:
  aggregation:
    enabled: false   # every aggregation check is reported as skipped
```

Listing a module that no check uses is an error (it is almost always a typo).

## `checks`

Each check is a mapping. These keys are common to every module:

| Key | Default | Meaning |
|---|---|---|
| `name` | required | Unique. Letters, digits, `_`, `.`, `-`; max 128 characters |
| `module` | required | `schema`, `aggregation`, `freshness` or `custom_sql` |
| `enabled` | `true` | `false` reports the check as `skipped` |
| `required` | `true` | `false` reports failures without failing the run |
| `description` | none | Free text shown in reports |
| `when` | none | Execution conditions, see below |

Every other key belongs to the module. See [Modules](#modules) below.

### `when`: execution conditions

All parts that are present must hold (logical AND). When they do not, the check is reported as `skipped` with the reason.

```yaml
when:
  env:
    TARGET: prod                       # must equal
    GITHUB_REF_NAME: [main, release]   # must equal one of
  depends_on: [orders_schema]          # these checks must have ended in success
  sql: SELECT COUNT(*) > 0 FROM orders # must return true or a non-zero number
```

| Part | Rules |
|---|---|
| `env` | Values are compared as strings. YAML `true`/`false` match the strings `"true"`/`"false"`. An unset variable never matches |
| `depends_on` | A name or a list of names. Dependencies must be declared **above** the check, so the run order is always the file order and cycles are impossible. A dependency that was skipped, failed, errored, or was filtered out of the run skips the dependent check |
| `sql` | Evaluated last, only if `env` and `depends_on` hold. `NULL` or no rows counts as false. A non-boolean, non-numeric result is reported as `error` |

## Modules

Table and column names are quoted for the target database, so `schema.table`, mixed case and reserved words work. Timestamp columns are assumed to hold UTC.

### `schema`

| Key | Default | Meaning |
|---|---|---|
| `table` | required | Table name, optionally `schema.table` |
| `columns` | required | Mapping of column name to spec (below). Names match case-insensitively |
| `allow_extra_columns` | `true` | `false` fails when the table has columns not listed |

Column spec: `type` (optional), `required` (default `true`: the column must exist), `nullable` (default `true`; `false` counts NULL values and fails if any).

Types compare case-insensitively with common synonyms: `int`/`integer`/`int4`, `bigint`/`int8`, `double`/`float8`/`double precision`, `varchar`/`text`/`string`, `boolean`/`bool`, `timestamp`/`datetime`, `decimal`/`numeric`. Without parentheses the size is ignored (`varchar` matches `VARCHAR(255)`); with parentheses it must match exactly (`decimal(18,2)`).

A missing table is a `failure`.

```yaml
- name: orders_schema
  module: schema
  table: orders
  columns:
    order_id: { type: integer, nullable: false }
    coupon_code: { type: varchar, required: false }
  allow_extra_columns: false
```

### `freshness`

| Key | Default | Meaning |
|---|---|---|
| `table` | required | |
| `timestamp_column` | required | |
| `max_age` | required | Duration: `90s`, `30m`, `24h`, `7d`, `2w`, or seconds |
| `where` | none | SQL filter applied before taking the newest timestamp |

Fails when the newest timestamp is older than `max_age` relative to the run's start, or when there are no rows.

### `aggregation`

| Key | Default | Meaning |
|---|---|---|
| `table` | required | |
| `function` | required | `count`, `count_distinct`, `sum`, `avg`, `min`, `max` |
| `column` | none | Required for every function except `count` (`count` without a column is `COUNT(*)`) |
| `where` | none | SQL filter |
| `period` | none | `{column, window}`: only rows in `[now - window, now)` |
| `condition` | | Compare the aggregate with a value: `"> 0"` or `{operator, value, tolerance}` |
| `compare_to_previous` | | `{max_relative_change}`: compare with the window before (`[now - 2*window, now - window)`). Needs `period` |

Exactly one of `condition` or `compare_to_previous`. A NULL aggregate (no matching rows) fails a `condition`. With `compare_to_previous`, NULL counts as 0; 0 in both periods passes, 0 then non-zero fails (the relative change is undefined).

Tolerance: `absolute` (same unit as the value) and/or `relative` (fraction of the value); the larger allowance wins. `{operator: "==", value: 1000, tolerance: {relative: 0.05}}` accepts 950 to 1050.

### `custom_sql`

| Key | Meaning |
|---|---|
| `sql` | Query returning exactly one row with one numeric or boolean column |
| `condition` | Same as aggregation |

No rows or NULL is a `failure`. More than one row or column, or a non-numeric value, is an `error`. Booleans count as 1 and 0.

```yaml
- name: no_negative_amounts
  module: custom_sql
  sql: SELECT COUNT(*) FROM orders WHERE amount < 0
  condition: "== 0"
```

## Environment variables

Any string value can reference environment variables:

| Syntax | Result |
|---|---|
| `${VAR}` | Value of `VAR`. The config is invalid if `VAR` is not set |
| `${VAR:-default}` | Value of `VAR`, or `default` when unset or empty |
| `$${VAR}` | The literal text `${VAR}` |

Interpolation happens after YAML parsing, on values only, so a variable can never inject YAML structure. `$1` and `$$` (common in SQL) are left untouched. Typed fields still validate after interpolation, so `enabled: ${RUN_SLOW:-false}` works.

Use variables for secrets instead of committing them:

```yaml
connection:
  type: sqlalchemy
  url: ${DATABASE_URL}
```

## Selecting checks

The order of decisions for each check:

1. CLI filters (`--only`, `--skip`, `--module`, Day 5) remove checks from the run and the report entirely. Unknown names are an error.
2. `enabled: false` on the check, or `enabled: false` on its module, reports it as `skipped`.
3. `when` is evaluated at run time, in file order.

## Errors

Invalid configuration exits with code `2` and lists every problem with its location:

```
Invalid configuration in modular-data-ci.yml (3 problems):
  - connection.pth: unknown key
  - checks[0] (orders_fresh).enabled: Input should be a valid boolean, unable to interpret input
  - checks[1] (b).when: 'when' needs at least one of 'env', 'depends_on' or 'sql'
```

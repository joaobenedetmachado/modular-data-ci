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
| `duckdb` | `path` (default `:memory:`), `read_only` (default `false`) |
| `sqlalchemy` | `url` (required). Needs `pip install modular-data-ci[sqlalchemy]` |

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

Every other key belongs to the module. Module params are documented with each module (Day 4).

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

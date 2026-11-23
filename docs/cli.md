# CLI reference

```
modular-data-ci [--version] <command> [options]
```

| Command | What it does |
|---|---|
| `run` | Run the configured checks, print a summary, write reports |
| `validate` | Load the config and validate every check's params, without opening the data source |
| `list` | Print the configured checks with module, enabled and required flags |
| `modules` | List available modules, including installed plugins |

## Finding the config

Every command that reads a config accepts `-c/--config PATH`. Without it, the CLI uses `$MDCI_CONFIG`, then the first of `modular-data-ci.yml`, `modular-data-ci.yaml`, `.modular-data-ci.yml` in the current directory.

## `run`

| Option | Meaning |
|---|---|
| `--report PATH` | Write the JSON report (directories are created) |
| `--junit PATH` | Write a JUnit XML report |
| `--only NAME` | Run only this check. Repeatable, or comma separated: `--only a,b` |
| `--skip NAME` | Leave this check out. Repeatable |
| `--module NAME` | Run only checks of this module. Repeatable |
| `-v`, `-vv` | Print details of checks that did not succeed (`-vv`: of every check) |
| `-q` | Print only failing and erroring checks, plus the totals |
| `--color auto\|always\|never` | `auto` colors when stdout is a terminal, honours `NO_COLOR` and `FORCE_COLOR` |

Checks left out with `--only`, `--skip` or `--module` do not appear in the report. Unknown names are an error (exit code 2).

Example output:

```
modular-data-ci 0.1.0
config: modular-data-ci.yml

  PASS  orders_schema [schema] - 5 columns match
  FAIL  orders_fresh [freshness] - newest row is 3d 2h old, expected at most 1d
  PASS  daily_orders_stable [aggregation] (optional) - ...
  SKIP  legacy_table_schema [schema] - disabled in config

4 checks: 2 passed, 1 failed, 0 errors, 1 skipped
RESULT: FAILED (1 blocking)
```

### Inside GitHub Actions

When `GITHUB_ACTIONS=true`, `run` also:

- prints `::error` annotations for failing required checks and `::warning` for optional ones, so they show up on the run and the pull request;
- appends a Markdown table to `$GITHUB_STEP_SUMMARY`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All required checks passed (or the command succeeded) |
| `1` | At least one required check ended in `failure` or `error` |
| `2` | Invalid arguments, configuration or selection; no checks were run |

## JSON report

```json
{
  "schema_version": 1,
  "tool_version": "0.1.0",
  "started_at": "2026-03-10T12:00:00Z",
  "finished_at": "2026-03-10T12:00:01Z",
  "config_path": "modular-data-ci.yml",
  "results": [
    {
      "name": "orders_fresh",
      "module": "freshness",
      "status": "failure",
      "required": true,
      "message": "newest row is 3d 2h old, expected at most 1d",
      "details": {"table": "orders", "age_seconds": 266400.0},
      "duration_ms": 3.2
    }
  ],
  "summary": {"total": 1, "success": 0, "failure": 1, "skipped": 0, "error": 0, "blocking": 1},
  "passed": false
}
```

`schema_version` changes only when a field is removed or changes meaning.

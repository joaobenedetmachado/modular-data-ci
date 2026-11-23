# GitHub Actions

The action runs the same `modular-data-ci run` you use locally. A required check that fails or errors fails the step, and therefore the job and the pull request check.

## With the action

```yaml
- uses: actions/checkout@v4
- uses: joaobenedetmachado/modular-data-ci@v0
  with:
    config: modular-data-ci.yml
    version: "0.1.0"
  env:
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

| Input | Default | Meaning |
|---|---|---|
| `config` | `""` | Config path. Empty: `$MDCI_CONFIG`, then `modular-data-ci.yml` |
| `report` | `modular-data-ci-report.json` | JSON report path |
| `junit` | `""` | Optional JUnit XML path |
| `args` | `""` | Extra `run` arguments, e.g. `--skip slow_check -v` |
| `version` | `local` | `0.1.0` installs from PyPI, `local` installs the action's own source, anything else is passed to `pip install` |
| `extras` | `""` | e.g. `sqlalchemy` |
| `python-version` | `3.12` | |

| Output | Meaning |
|---|---|
| `passed` | `"true"` when every required check passed |
| `report` | JSON report path |

Inputs reach the shell only through environment variables, never by direct interpolation, so a config path cannot inject commands.

## Without the action

```yaml
- uses: actions/setup-python@v5
  with: { python-version: "3.12" }
- run: pip install "modular-data-ci[sqlalchemy]" "psycopg[binary]"
- run: modular-data-ci run --report report.json
  env:
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

## What shows up in GitHub

- **Annotations:** failing required checks as errors, failing optional checks as warnings, attached to the config file.
- **Job summary:** a table with every check, its status and message.
- **Artifacts:** upload `modular-data-ci-report.json` (and `junit.xml`) with `actions/upload-artifact` to keep them.

## Recipes

Keep warnings from blocking a merge: mark the check `required: false`.

Run a check only on the main branch:

```yaml
when:
  env: { GITHUB_REF_NAME: main }
```

Check data on a schedule, not only on pushes:

```yaml
on:
  schedule:
    - cron: "0 6 * * *"
```

React to the result in later steps:

```yaml
- id: dq
  uses: joaobenedetmachado/modular-data-ci@v0
  continue-on-error: true
- if: steps.dq.outputs.passed != 'true'
  run: echo "data quality failed, notifying..."
```

Ready-to-copy workflows: [`examples/workflows/`](../examples/workflows/). This repository's own [`action-e2e.yml`](../.github/workflows/action-e2e.yml) runs the action against healthy and broken sample data and asserts that the second one fails.

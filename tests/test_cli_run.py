import json
from pathlib import Path

import duckdb
import pytest

from modular_data_ci.cli import main


@pytest.fixture
def project(tmp_path, monkeypatch):
    db = tmp_path / "data.duckdb"
    with duckdb.connect(str(db)) as conn:
        conn.execute("CREATE TABLE t AS SELECT * FROM range(5) r(x)")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write_config(path: Path, condition: str) -> Path:
    path.write_text(
        f"""
connection: {{type: duckdb, path: data.duckdb}}
checks:
  - name: rows
    module: custom_sql
    sql: SELECT COUNT(*) FROM t
    condition: "{condition}"
"""
    )
    return path


def test_run_passes(project, capsys):
    write_config(project / "modular-data-ci.yml", "== 5")
    assert main(["run"]) == 0
    assert "RESULT: PASSED" in capsys.readouterr().out


def test_run_fails_with_exit_code_1_and_writes_report(project, capsys):
    cfg = write_config(project / "c.yml", "> 10")
    assert main(["run", "--config", str(cfg), "--report", "out/r.json"]) == 1
    data = json.loads((project / "out" / "r.json").read_text())
    assert data["passed"] is False
    assert "RESULT: FAILED" in capsys.readouterr().out


def test_invalid_config_exits_2(project, capsys):
    (project / "bad.yml").write_text("checks: []\n")
    assert main(["run", "-c", "bad.yml"]) == 2
    assert "Invalid configuration" in capsys.readouterr().err


def test_missing_config_exits_2(project, capsys):
    assert main(["run"]) == 2
    assert "file not found" in capsys.readouterr().err


def test_filters(project, capsys):
    (project / "modular-data-ci.yml").write_text(
        """
connection: {type: duckdb, path: data.duckdb}
checks:
  - {name: a, module: custom_sql, sql: SELECT 1, condition: "== 1"}
  - {name: b, module: custom_sql, sql: SELECT 1, condition: "== 2"}
  - {name: c, module: freshness, table: t, timestamp_column: x, max_age: 1h}
"""
    )
    assert main(["run", "--only", "a"]) == 0
    out = capsys.readouterr().out
    assert " a [" in out
    assert " b [" not in out
    assert main(["run", "--skip", "b,c"]) == 0
    assert main(["run", "--module", "custom_sql"]) == 1


def test_unknown_filter_exits_2(project, capsys):
    write_config(project / "modular-data-ci.yml", "== 5")
    assert main(["run", "--only", "nope"]) == 2
    assert "unknown check(s): nope" in capsys.readouterr().err


def test_finds_yaml_extension(project):
    write_config(project / "modular-data-ci.yaml", "== 5")
    assert main(["run"]) == 0


def test_config_from_env(project, monkeypatch):
    write_config(project / "elsewhere.yml", "== 5")
    monkeypatch.setenv("MDCI_CONFIG", "elsewhere.yml")
    assert main(["run"]) == 0


def test_unwritable_report_exits_2(project, capsys):
    write_config(project / "modular-data-ci.yml", "== 5")
    (project / "file").write_text("")
    assert main(["run", "--report", "file/report.json"]) == 2
    assert "cannot write report" in capsys.readouterr().err


def test_ctrl_c_exits_130(project, monkeypatch, capsys):
    import modular_data_ci.cli as cli

    def interrupt(args):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_run", interrupt)
    assert main(["run"]) == 130


def test_dry_run_does_not_connect(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "modular-data-ci.yml").write_text(
        """
connection: {type: duckdb, path: missing.duckdb}
checks:
  - {name: a, module: custom_sql, sql: SELECT 1, condition: "== 1"}
  - {name: b, module: custom_sql, sql: SELECT 1, condition: "== 1", enabled: false}
  - {name: c, module: custom_sql, sql: SELECT 1, condition: "== 1", when: {depends_on: a}}
"""
    )
    assert main(["run", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "run   a [custom_sql]" in out
    assert "skip  b [custom_sql] - disabled in config" in out
    assert "run   c [custom_sql] (has when)" in out
    assert "2 of 3 selected checks would run" in out


def test_fail_fast_skips_the_rest(project, capsys):
    (project / "modular-data-ci.yml").write_text(
        """
connection: {type: duckdb, path: data.duckdb}
checks:
  - {name: a, module: custom_sql, sql: SELECT 1, condition: "== 2", required: false}
  - {name: b, module: custom_sql, sql: SELECT 1, condition: "== 2"}
  - {name: c, module: custom_sql, sql: SELECT 1, condition: "== 1"}
"""
    )
    assert main(["run", "-x"]) == 1
    out = capsys.readouterr().out
    assert "FAIL  a" in out
    assert "FAIL  b" in out
    assert "SKIP  c [custom_sql] - not run: an earlier required check failed" in out


def test_format_json_prints_report(project, capsys, monkeypatch):
    write_config(project / "modular-data-ci.yml", "> 10")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert main(["run", "--format", "json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["results"][0]["name"] == "rows"


def test_env_file(project):
    (project / "modular-data-ci.yml").write_text(
        """
connection: {type: duckdb, path: "${DB_FILE}"}
checks:
  - {name: a, module: custom_sql, sql: SELECT COUNT(*) FROM t, condition: "== 5"}
"""
    )
    (project / ".env").write_text("DB_FILE=data.duckdb\n")
    assert main(["run"]) == 2
    assert main(["run", "--env-file", ".env"]) == 0
    assert main(["validate", "--env-file", ".env"]) == 0

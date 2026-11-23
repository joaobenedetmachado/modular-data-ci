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

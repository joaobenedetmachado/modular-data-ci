from modular_data_ci.cli import main


def test_validate_ok_without_database(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "modular-data-ci.yml").write_text(
        """
connection: {type: duckdb, path: does-not-exist.duckdb}
checks:
  - {name: a, module: custom_sql, sql: SELECT 1, condition: "== 1"}
  - {name: b, module: custom_sql, sql: SELECT 1, condition: "== 1", enabled: false}
"""
    )
    assert main(["validate"]) == 0
    assert "OK (2 checks, 1 enabled)" in capsys.readouterr().out


def test_validate_reports_module_param_errors(tmp_path, capsys):
    cfg = tmp_path / "c.yml"
    cfg.write_text(
        """
connection: {type: duckdb}
checks:
  - {name: a, module: custom_sql, sql: SELECT 1, conditon: "== 1"}
"""
    )
    assert main(["validate", "-c", str(cfg)]) == 2
    err = capsys.readouterr().err
    assert "checks[0] (a).conditon: unknown key" in err

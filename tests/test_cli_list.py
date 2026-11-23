from modular_data_ci.cli import main


def test_list_checks(tmp_path, capsys):
    cfg = tmp_path / "c.yml"
    cfg.write_text(
        """
connection: {type: duckdb}
modules: {freshness: {enabled: false}}
checks:
  - {name: a, module: custom_sql, sql: SELECT 1, condition: "== 1", description: First}
  - {name: b, module: freshness, table: t, timestamp_column: ts, max_age: 1h, required: false}
"""
    )
    assert main(["list", "-c", str(cfg)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["NAME", "MODULE", "ENABLED", "REQUIRED", "DESCRIPTION"]
    assert lines[1].split() == ["a", "custom_sql", "yes", "yes", "First"]
    assert lines[2].split() == ["b", "freshness", "no", "no"]

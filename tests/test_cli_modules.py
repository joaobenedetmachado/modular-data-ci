from modular_data_ci.cli import main


def test_modules_lists_builtins(capsys):
    assert main(["modules"]) == 0
    out = capsys.readouterr().out
    for name in ("aggregation", "custom_sql", "freshness", "schema"):
        assert name in out
    assert "Freshness module" in out

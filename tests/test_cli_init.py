import pytest

from modular_data_ci.cli import main
from modular_data_ci.config import parse_config
from modular_data_ci.registry import ModuleRegistry, resolve_checks
from modular_data_ci.scaffold import starter_config


@pytest.mark.parametrize("kind", ["duckdb", "sqlalchemy"])
def test_starter_config_is_valid(kind):
    config = parse_config(
        starter_config(connection_type=kind, table="orders"), env={"DATABASE_URL": "sqlite://"}
    )
    assert config.checks[0].name == "orders_not_empty"
    resolve_checks(config, ModuleRegistry.default())


def test_init_writes_and_refuses_overwrite(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--table", "events"]) == 0
    assert "events_ids_unique" in (tmp_path / "modular-data-ci.yml").read_text()
    assert main(["init"]) == 2
    assert "already exists" in capsys.readouterr().err
    assert main(["init", "--force"]) == 0

from pathlib import Path

import pytest

from modular_data_ci.config import load_config
from modular_data_ci.engine import Engine

ROOT = Path(__file__).parent.parent


def test_csv_example_runs(monkeypatch):
    monkeypatch.chdir(ROOT)
    report = Engine().run(load_config("examples/csv/modular-data-ci.yml", env={}))
    statuses = {r.name: r.status.value for r in report.results}
    assert statuses.pop("low_stock") == "failure"  # optional: reported, does not block
    assert set(statuses.values()) == {"success"}
    assert report.passed


@pytest.mark.parametrize("name", ["sku_format", "known_categories"])
def test_csv_example_has_check(name):
    config = load_config(ROOT / "examples/csv/modular-data-ci.yml", env={})
    assert config.get_check(name)

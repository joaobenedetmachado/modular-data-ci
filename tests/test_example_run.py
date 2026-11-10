"""End to end: the example config against the generated sample database."""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

from modular_data_ci.config import load_config
from modular_data_ci.engine import Engine

ROOT = Path(__file__).parent.parent
NOW = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def _make_sample_db():
    spec = importlib.util.spec_from_file_location(
        "make_sample_db", ROOT / "examples" / "make_sample_db.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(tmp_path: Path, *, broken: bool, env: dict[str, str] | None = None):
    db = tmp_path / "shop.duckdb"
    _make_sample_db().build(db, now=NOW, broken=broken)
    env = {"MDCI_DUCKDB_PATH": str(db), **(env or {})}
    config = load_config(ROOT / "examples" / "modular-data-ci.yml", env=env)
    return Engine(clock=lambda: NOW, env=env).run(config)


def _statuses(report):
    return {r.name: r.status.value for r in report.results}


def test_healthy_data_passes(tmp_path):
    report = _run(tmp_path, broken=False)
    assert _statuses(report) == {
        "orders_schema": "success",
        "orders_fresh": "success",
        "revenue_matches_target": "success",
        "daily_orders_stable": "success",
        "no_negative_amounts": "success",
        "prod_only_coupon_check": "skipped",
        "legacy_table_schema": "skipped",
    }
    assert report.passed


def test_prod_only_check_runs_with_matching_env(tmp_path):
    report = _run(tmp_path, broken=False, env={"TARGET": "prod", "GITHUB_REF_NAME": "main"})
    assert _statuses(report)["prod_only_coupon_check"] == "success"


def test_broken_data_fails_the_run(tmp_path):
    report = _run(tmp_path, broken=True)
    statuses = _statuses(report)
    assert statuses["orders_schema"] == "success"
    assert statuses["orders_fresh"] == "failure"
    assert statuses["revenue_matches_target"] == "failure"
    assert statuses["no_negative_amounts"] == "failure"
    assert not report.passed
    assert report.exit_code == 1
    negatives = next(r for r in report.results if r.name == "no_negative_amounts")
    assert negatives.message == "value 3, expected == 0"


@pytest.mark.parametrize("broken", [False, True])
def test_report_is_json_serializable(tmp_path, broken):
    assert '"results"' in _run(tmp_path, broken=broken).model_dump_json()

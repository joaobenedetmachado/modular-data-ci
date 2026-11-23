"""The installed CLI against the example config, in a real subprocess."""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.test_example_run import _make_sample_db

ROOT = Path(__file__).parent.parent
CONFIG = ROOT / "examples" / "modular-data-ci.yml"


def _cli(tmp_path: Path, *, broken: bool, extra_env=None):
    db = tmp_path / "shop.duckdb"
    _make_sample_db().build(db, now=datetime.now(timezone.utc), broken=broken)
    env = {**os.environ, "MDCI_DUCKDB_PATH": str(db), "NO_COLOR": "1"}
    env.pop("GITHUB_ACTIONS", None)
    env.pop("GITHUB_STEP_SUMMARY", None)
    env.update(extra_env or {})
    report = tmp_path / "report.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "modular_data_ci",
            "run",
            "-c",
            str(CONFIG),
            "--report",
            str(report),
            "--junit",
            str(tmp_path / "junit.xml"),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return completed, json.loads(report.read_text())


def test_healthy_run_exits_0(tmp_path):
    completed, report = _cli(tmp_path, broken=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "RESULT: PASSED" in completed.stdout
    assert report["summary"]["success"] == 5
    assert (tmp_path / "junit.xml").exists()


def test_broken_run_exits_1(tmp_path):
    completed, report = _cli(tmp_path, broken=True)
    assert completed.returncode == 1
    assert "FAIL  no_negative_amounts" in completed.stdout
    assert report["passed"] is False


@pytest.mark.parametrize("broken", [False, True])
def test_github_annotations_only_on_failure(tmp_path, broken):
    completed, _ = _cli(tmp_path, broken=broken, extra_env={"GITHUB_ACTIONS": "true"})
    assert ("::error " in completed.stdout) is broken

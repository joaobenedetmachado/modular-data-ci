import subprocess
import sys

import pytest

from modular_data_ci import __version__
from modular_data_ci.cli import main


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_arguments_prints_help(capsys):
    assert main([]) == 0
    assert "usage: modular-data-ci" in capsys.readouterr().out


def test_module_entry_point_runs():
    completed = subprocess.run(
        [sys.executable, "-m", "modular_data_ci", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "modular-data-ci" in completed.stdout

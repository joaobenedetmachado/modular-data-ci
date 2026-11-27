import pytest

from modular_data_ci.config.env_file import merged_env, read_env_file
from modular_data_ci.errors import ConfigError


def test_read_env_file(tmp_path):
    path = tmp_path / ".env"
    path.write_text("# comment\n\nA=1\nexport B = two words # note\nC='quoted # kept'\nD=\"x\"\n")
    assert read_env_file(path) == {"A": "1", "B": "two words", "C": "quoted # kept", "D": "x"}


def test_bad_lines_reported(tmp_path):
    path = tmp_path / ".env"
    path.write_text("OK=1\nnot a pair\n")
    with pytest.raises(ConfigError, match="line 2: expected KEY=value"):
        read_env_file(path)


def test_real_environment_wins(tmp_path):
    first, second = tmp_path / "a.env", tmp_path / "b.env"
    first.write_text("X=a\nY=a\n")
    second.write_text("Y=b\nZ=b\n")
    assert merged_env({"Z": "env"}, [first, second]) == {"X": "a", "Y": "b", "Z": "env"}

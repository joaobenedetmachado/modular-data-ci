"""Static checks on the composite GitHub Action."""

from pathlib import Path

import yaml

ACTION = yaml.safe_load((Path(__file__).parent.parent / "action.yml").read_text())


def test_action_is_composite_with_expected_inputs():
    assert ACTION["runs"]["using"] == "composite"
    assert set(ACTION["inputs"]) >= {"config", "report", "junit", "args", "version"}
    assert "passed" in ACTION["outputs"]


def test_inputs_reach_scripts_only_through_env():
    """Interpolating ${{ inputs.* }} into `run:` would allow script injection."""
    for step in ACTION["runs"]["steps"]:
        assert "${{" not in step.get("run", ""), step.get("name")


def test_example_workflows_are_valid_yaml():
    folder = Path(__file__).parent.parent / "examples" / "workflows"
    files = sorted(folder.glob("*.yml"))
    assert files
    for path in files:
        workflow = yaml.safe_load(path.read_text())
        assert workflow["jobs"], path.name

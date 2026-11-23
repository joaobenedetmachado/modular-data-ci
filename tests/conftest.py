import pytest


@pytest.fixture(autouse=True)
def _isolate_ci_environment(monkeypatch):
    """Tests run inside GitHub Actions too; keep CLI output independent of it."""
    for name in ("GITHUB_ACTIONS", "GITHUB_STEP_SUMMARY", "MDCI_CONFIG", "NO_COLOR", "FORCE_COLOR"):
        monkeypatch.delenv(name, raising=False)

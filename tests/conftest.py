import pytest

from tests.module_fixtures import make_context


@pytest.fixture(autouse=True)
def _isolate_ci_environment(monkeypatch):
    """Tests run inside GitHub Actions too; keep CLI output independent of it."""
    for name in ("GITHUB_ACTIONS", "GITHUB_STEP_SUMMARY", "MDCI_CONFIG", "NO_COLOR", "FORCE_COLOR"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def users():
    context = make_context(
        "CREATE TABLE users (id INTEGER, email VARCHAR, country VARCHAR, age INTEGER)",
        """INSERT INTO users VALUES
            (1, 'a@x.com', 'BR', 30),
            (2, 'b@x.com', 'US', 41),
            (3, NULL,      'BR', NULL),
            (4, 'd@x.com', 'XX', 17),
            (4, 'e@x.com', 'US', 25)""",
    )
    yield context
    context.source.close()

import pytest
from fastapi.testclient import TestClient

from asset_manager.bridge.server import app

# Legacy mapgen_agents-era tests under tests/legacy/ are quarantined - they
# import from the removed mapgen_agents.* namespace and would fail at
# collection. Skip them by default; running them explicitly via
# `pytest tests/legacy/` will still surface the import errors for any future
# port effort.
collect_ignore_glob = ["legacy/*"]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

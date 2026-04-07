import pytest
from fastapi.testclient import TestClient

from asset_manager.bridge.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

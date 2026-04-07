"""Gateway tests.

Both gateways need real external services to fully exercise (an
AUTOMATIC1111 server for SD, an API key + cloud account for Scenario).
These tests cover everything that DOESN'T need those: construction,
is_available() reporting False on missing credentials, generate()
raising GatewayUnavailable on unreachable endpoints.

The reachable-and-working path can be tested manually by anyone with
the credentials.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from asset_manager.gateway.base import GatewayUnavailable
from asset_manager.gateway.scenario import ScenarioGateway
from asset_manager.gateway.stable_diffusion import StableDiffusionGateway

# ---------------------------------------------------------------- StableDiffusionGateway


def test_sd_gateway_default_construction():
    gw = StableDiffusionGateway()
    assert gw.name == "stable_diffusion"


def test_sd_gateway_unreachable_reports_unavailable():
    """Pointing at a port nothing's listening on, is_available returns False."""
    gw = StableDiffusionGateway(base_url="http://127.0.0.1:7999")
    assert gw.is_available() is False


def test_sd_gateway_generate_raises_when_unreachable(tmp_path: Path):
    gw = StableDiffusionGateway(base_url="http://127.0.0.1:7999")
    with pytest.raises(GatewayUnavailable) as exc_info:
        gw.generate("a goblin", tmp_path / "x.png")
    assert "unreachable" in str(exc_info.value)


def test_sd_gateway_respects_constructor_overrides():
    gw = StableDiffusionGateway(base_url="http://example.com:9999/", timeout=1.5)
    # Trailing slash trimmed
    assert gw._base_url == "http://example.com:9999"
    assert gw._timeout == 1.5


# ---------------------------------------------------------------- ScenarioGateway


def test_scenario_gateway_default_construction(monkeypatch):
    monkeypatch.delenv("SCENARIO_API_KEY", raising=False)
    monkeypatch.delenv("SCENARIO_MODEL_ID", raising=False)
    gw = ScenarioGateway()
    assert gw.name == "scenario"
    assert gw._api_key is None


def test_scenario_gateway_unavailable_without_api_key(monkeypatch):
    monkeypatch.delenv("SCENARIO_API_KEY", raising=False)
    gw = ScenarioGateway()
    assert gw.is_available() is False


def test_scenario_gateway_generate_raises_without_api_key(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("SCENARIO_API_KEY", raising=False)
    gw = ScenarioGateway()
    with pytest.raises(GatewayUnavailable) as exc_info:
        gw.generate("a sword icon", tmp_path / "x.png")
    assert "SCENARIO_API_KEY" in str(exc_info.value)


def test_scenario_gateway_generate_raises_without_model_id(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SCENARIO_API_KEY", "fake-key")
    monkeypatch.delenv("SCENARIO_MODEL_ID", raising=False)
    gw = ScenarioGateway()
    with pytest.raises(GatewayUnavailable) as exc_info:
        gw.generate("a sword icon", tmp_path / "x.png")
    assert "SCENARIO_MODEL_ID" in str(exc_info.value)


def test_scenario_gateway_respects_constructor_overrides():
    gw = ScenarioGateway(
        api_key="explicit-key",
        model_id="model-123",
        base_url="https://example.com/v2/",
        timeout=10.0,
    )
    assert gw._api_key == "explicit-key"
    assert gw._model_id == "model-123"
    assert gw._base_url == "https://example.com/v2"
    assert gw._timeout == 10.0

"""Tests for the new Tripo3D and Nano Banana gateways.

These tests verify the unavailable-without-key behavior and basic
construction. They do NOT make real API calls — that requires the
user's API keys and would burn credits. The actual integration tests
will run when keys are provided.
"""

from __future__ import annotations

import pytest

from asset_manager.gateway.base import GatewayUnavailable
from asset_manager.gateway.nano_banana import NanoBananaGateway
from asset_manager.gateway.tripo3d import Tripo3DGateway

# ─── Tripo3D gateway ────────────────────────────────────────────────


def test_tripo3d_unavailable_without_api_key(monkeypatch):
    monkeypatch.delenv("TRIPO_API_KEY", raising=False)
    gw = Tripo3DGateway()
    assert gw.is_available() is False


def test_tripo3d_available_with_api_key(monkeypatch):
    monkeypatch.setenv("TRIPO_API_KEY", "fake-key-for-testing")
    gw = Tripo3DGateway()
    assert gw.is_available() is True


def test_tripo3d_generate_raises_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("TRIPO_API_KEY", raising=False)
    gw = Tripo3DGateway()
    with pytest.raises(GatewayUnavailable, match="TRIPO_API_KEY"):
        gw.generate("a wolf", tmp_path / "wolf.glb")


def test_tripo3d_image_mode_requires_image_path(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIPO_API_KEY", "fake-key-for-testing")
    gw = Tripo3DGateway()
    with pytest.raises(GatewayUnavailable, match="image_path"):
        gw.generate("style hint", tmp_path / "out.glb", mode="image")


def test_tripo3d_image_mode_rejects_missing_image(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIPO_API_KEY", "fake-key-for-testing")
    gw = Tripo3DGateway()
    with pytest.raises(GatewayUnavailable, match="does not exist"):
        gw.generate(
            "style hint",
            tmp_path / "out.glb",
            mode="image",
            image_path=tmp_path / "missing.png",
        )


def test_tripo3d_unsupported_mode_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIPO_API_KEY", "fake-key-for-testing")
    gw = Tripo3DGateway()
    with pytest.raises(GatewayUnavailable, match="unsupported mode"):
        gw.generate("a wolf", tmp_path / "out.glb", mode="hologram")


# ─── Nano Banana gateway ────────────────────────────────────────────


def test_nano_banana_unavailable_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gw = NanoBananaGateway()
    assert gw.is_available() is False


def test_nano_banana_available_with_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-testing")
    gw = NanoBananaGateway()
    assert gw.is_available() is True


def test_nano_banana_generate_raises_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gw = NanoBananaGateway()
    with pytest.raises(GatewayUnavailable, match="GEMINI_API_KEY"):
        gw.generate("a wolf", tmp_path / "wolf.png")


def test_nano_banana_image_mode_requires_image_path(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-testing")
    gw = NanoBananaGateway()
    with pytest.raises(GatewayUnavailable, match="image_path"):
        gw.generate("edit prompt", tmp_path / "out.png", mode="image")


def test_nano_banana_image_mode_rejects_missing_image(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-testing")
    gw = NanoBananaGateway()
    with pytest.raises(GatewayUnavailable, match="does not exist"):
        gw.generate(
            "edit prompt",
            tmp_path / "out.png",
            mode="image",
            image_path=tmp_path / "missing.png",
        )


def test_nano_banana_unsupported_mode_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-testing")
    gw = NanoBananaGateway()
    with pytest.raises(GatewayUnavailable, match="unsupported mode"):
        gw.generate("a wolf", tmp_path / "out.png", mode="hologram")

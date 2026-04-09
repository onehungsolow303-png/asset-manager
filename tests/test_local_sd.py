"""Tests for the local SD + LoRA gateway stub."""
from __future__ import annotations

from pathlib import Path

import pytest

from asset_manager.gateway.base import GatewayUnavailable
from asset_manager.generators.local_sd import LocalSDGateway


def test_unavailable_without_lora_name(tmp_path):
    gw = LocalSDGateway(training_root=tmp_path)
    assert gw.is_available() is False


def test_unavailable_when_lora_not_trained(tmp_path):
    gw = LocalSDGateway(lora_name="dnd_style", training_root=tmp_path)
    assert gw.is_available() is False
    assert gw.list_available_loras() == []


def test_unavailable_even_with_trained_lora_until_backend_wired(tmp_path):
    """Until the webui backend integration lands, is_available() returns
    False even when a LoRA exists. This is the deliberate stub behavior
    so the source_decision router cleanly falls through to cloud tiers."""
    (tmp_path / "dnd_style" / "checkpoints").mkdir(parents=True)
    gw = LocalSDGateway(lora_name="dnd_style", training_root=tmp_path)
    assert gw.list_available_loras() == ["dnd_style"]
    # Backend not wired yet
    assert gw.is_available() is False


def test_generate_raises_without_lora_name(tmp_path):
    gw = LocalSDGateway(training_root=tmp_path)
    with pytest.raises(GatewayUnavailable, match="lora_name"):
        gw.generate("a wolf", tmp_path / "out.png")


def test_generate_raises_when_lora_missing(tmp_path):
    gw = LocalSDGateway(lora_name="missing_lora", training_root=tmp_path)
    with pytest.raises(GatewayUnavailable, match="not yet trained"):
        gw.generate("a wolf", tmp_path / "out.png")


def test_generate_raises_not_yet_implemented_with_trained_lora(tmp_path):
    """When the LoRA exists but the webui isn't wired, generate() raises
    a clear 'not yet implemented' error so the user knows what's missing."""
    (tmp_path / "dnd_style" / "checkpoints").mkdir(parents=True)
    gw = LocalSDGateway(lora_name="dnd_style", training_root=tmp_path)
    with pytest.raises(GatewayUnavailable, match="not yet implemented"):
        gw.generate("a wolf", tmp_path / "out.png")


def test_list_available_loras_finds_trained(tmp_path):
    (tmp_path / "lora_a" / "checkpoints").mkdir(parents=True)
    (tmp_path / "lora_b" / "checkpoints").mkdir(parents=True)
    gw = LocalSDGateway(training_root=tmp_path)
    loras = gw.list_available_loras()
    assert "lora_a" in loras
    assert "lora_b" in loras

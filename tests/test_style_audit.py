"""Tests for the style audit / quality gate."""
from __future__ import annotations

import pytest
from pathlib import Path

from asset_manager.pipeline.style_audit import (
    AuditPolicy,
    AuditReport,
    audit,
)


def _write_test_png(path: Path, size: int = 32, mode: str = "RGBA") -> Path:
    from PIL import Image
    color = (200, 100, 50, 255) if mode == "RGBA" else (200, 100, 50)
    img = Image.new(mode, (size, size), color)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")
    return path


# ─── Pass cases ────────────────────────────────────────────────────

def test_well_formed_creature_token_passes(tmp_path):
    p = _write_test_png(tmp_path / "wolf.png", size=32, mode="RGBA")
    report = audit("wolf", "creature_token", p)
    assert report.passed is True
    assert report.failures == []


def test_well_formed_item_icon_passes(tmp_path):
    p = _write_test_png(tmp_path / "potion.png", size=16, mode="RGBA")
    report = audit("potion", "item_icon", p)
    assert report.passed is True


# ─── File existence ───────────────────────────────────────────────

def test_missing_file_fails(tmp_path):
    report = audit("ghost", "creature_token", tmp_path / "ghost.png")
    assert report.passed is False
    assert any("does not exist" in f for f in report.failures)


# ─── Extension check ───────────────────────────────────────────────

def test_wrong_extension_for_creature_token_fails(tmp_path):
    p = tmp_path / "wolf.glb"
    p.write_bytes(b"fake glb")
    report = audit("wolf", "creature_token", p)
    assert report.passed is False
    assert any("extension" in f for f in report.failures)


def test_glb_passes_for_dungeon_tile_kind(tmp_path):
    p = tmp_path / "wall.glb"
    p.write_bytes(b"fake glb content with enough bytes")
    report = audit("wall", "dungeon_tile", p,
                    policy=AuditPolicy(check_image_loadable=False))
    assert report.passed is True or "extension" not in str(report.failures)


# ─── Dimensions ────────────────────────────────────────────────────

def test_too_small_creature_token_fails(tmp_path):
    p = _write_test_png(tmp_path / "tiny.png", size=8)
    report = audit("tiny", "creature_token", p)
    assert report.passed is False
    assert any("below min" in f for f in report.failures)


def test_too_large_item_icon_fails(tmp_path):
    p = _write_test_png(tmp_path / "huge.png", size=512)
    report = audit("huge", "item_icon", p)
    assert report.passed is False
    assert any("exceed max" in f for f in report.failures)


# ─── Alpha channel ─────────────────────────────────────────────────

def test_creature_token_without_alpha_fails(tmp_path):
    p = _write_test_png(tmp_path / "opaque.png", size=32, mode="RGB")
    report = audit("opaque", "creature_token", p)
    assert report.passed is False
    assert any("alpha channel" in f for f in report.failures)


# ─── Naming convention ────────────────────────────────────────────

def test_empty_asset_id_fails(tmp_path):
    p = _write_test_png(tmp_path / "wolf.png")
    report = audit("", "creature_token", p)
    assert report.passed is False
    assert any("empty" in f for f in report.failures)


def test_asset_id_with_spaces_fails(tmp_path):
    p = _write_test_png(tmp_path / "wolf.png")
    report = audit("dire wolf", "creature_token", p)
    assert report.passed is False
    assert any("spaces" in f for f in report.failures)


def test_uppercase_asset_id_warns_but_passes(tmp_path):
    p = _write_test_png(tmp_path / "wolf.png")
    report = audit("Wolf", "creature_token", p)
    assert report.passed is True
    assert any("uppercase" in w for w in report.warnings)


# ─── Manifest provenance ──────────────────────────────────────────

def test_manifest_missing_source_warns(tmp_path):
    p = _write_test_png(tmp_path / "wolf.png")
    manifest = {"path": str(p)}  # missing source/license
    report = audit("wolf", "creature_token", p, manifest=manifest)
    assert any("source" in w for w in report.warnings)
    assert any("license" in w for w in report.warnings)


def test_ai_source_without_prompt_warns(tmp_path):
    p = _write_test_png(tmp_path / "wolf.png")
    manifest = {"source": "ai_2d", "license": "user_owned", "path": str(p)}
    report = audit("wolf", "creature_token", p, manifest=manifest)
    assert any("prompt" in w for w in report.warnings)


# ─── Catalog uniqueness ───────────────────────────────────────────

def test_duplicate_asset_id_with_different_path_warns(tmp_path):
    class FakeCatalog:
        def get(self, _id):
            return {"path": "/different/path.png"}

    p = _write_test_png(tmp_path / "wolf.png")
    report = audit("wolf", "creature_token", p, catalog=FakeCatalog())
    assert any("already in catalog" in w for w in report.warnings)


# ─── Policy switches ──────────────────────────────────────────────

def test_disabled_check_does_not_run(tmp_path):
    p = _write_test_png(tmp_path / "tiny.png", size=8)
    policy = AuditPolicy(check_dimensions=False)
    report = audit("tiny", "creature_token", p, policy=policy)
    # Dimensions check skipped, so no failure on small size
    assert not any("below min" in f for f in report.failures)

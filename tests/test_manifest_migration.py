"""Tests for manifest schema migration.

Verifies that legacy catalog entries (just {asset_id, kind, path}) are
upgraded in-place to the new provenance schema (source, license, etc.)
on Catalog load, and that already-migrated entries are no-ops.
"""

from __future__ import annotations

from pathlib import Path

from asset_manager.library.manifest import (
    is_modern_manifest,
    make_manifest,
    migrate_manifest,
)

# ─── make_manifest ─────────────────────────────────────────────────


def test_make_manifest_minimal_args_includes_defaults():
    m = make_manifest(asset_id="wolf", kind="creature_token", path="/tmp/wolf.png")
    assert m["asset_id"] == "wolf"
    assert m["kind"] == "creature_token"
    assert m["path"] == "/tmp/wolf.png"
    assert m["source"] == "unknown"
    assert m["license"] == "unknown"
    assert m["cost_usd"] == 0.0
    assert m["swap_safe"] is True
    assert m["generator_version"] == "v1"
    assert m["redistribution"] is True
    assert "generated_at" in m


def test_make_manifest_with_full_provenance():
    m = make_manifest(
        asset_id="garth_portrait",
        kind="portrait",
        path="/tmp/garth.png",
        source="ai_2d",
        license="Scenario_owned",
        cost_usd=0.04,
        prompt="weathered hunter, sixties, blunt expression",
        swap_safe=False,  # AI portraits user might curate
    )
    assert m["source"] == "ai_2d"
    assert m["license"] == "Scenario_owned"
    assert m["cost_usd"] == 0.04
    assert m["prompt"] == "weathered hunter, sixties, blunt expression"
    assert m["swap_safe"] is False


def test_make_manifest_extra_kwargs_pass_through():
    m = make_manifest(
        asset_id="x",
        kind="y",
        path="/p",
        custom_field="custom_value",
    )
    assert m["custom_field"] == "custom_value"


# ─── migrate_manifest ─────────────────────────────────────────────


def test_legacy_manifest_gets_default_fields():
    legacy = {"asset_id": "wolf", "kind": "creature_token", "path": "/tmp/wolf.png"}
    migrated = migrate_manifest(legacy)
    assert migrated["source"] == "unknown"  # path doesn't match any inference rule
    assert migrated["license"] == "unknown"
    assert migrated["cost_usd"] == 0.0
    assert migrated["swap_safe"] is True
    assert migrated["redistribution"] is True
    assert "generated_at" in migrated


def test_kaykit_path_infers_pack_source_and_license():
    legacy = {
        "asset_id": "kaykit_dungeon_wall",
        "kind": "dungeon_tile",
        "path": "C:/Dev/.shared/baked/packs/kaykit/dungeon/wall.glb",
    }
    migrated = migrate_manifest(legacy)
    assert migrated["source"] == "pack"
    assert migrated["pack_name"] == "kaykit"
    assert migrated["license"] == "KayKit_free"
    assert migrated["redistribution"] is True


def test_synty_path_infers_restricted_redistribution():
    legacy = {
        "asset_id": "synty_fk_villager",
        "kind": "character",
        "path": "C:/Dev/.shared/baked/packs/synty/fantasy_kingdom/villager.fbx",
    }
    migrated = migrate_manifest(legacy)
    assert migrated["source"] == "pack"
    assert migrated["pack_name"] == "synty"
    assert migrated["license"] == "Synty_standard"
    assert migrated["redistribution"] is False  # critical


def test_kenney_path_infers_cc0():
    legacy = {
        "asset_id": "kenney_tile",
        "kind": "tile",
        "path": "C:/Dev/.shared/baked/packs/kenney/medieval/tile.png",
    }
    migrated = migrate_manifest(legacy)
    assert migrated["source"] == "pack"
    assert migrated["license"] == "CC0"


def test_seed_pipeline_path_infers_procedural():
    legacy = {
        "asset_id": "wolf",
        "kind": "creature_token",
        "path": "C:/Dev/.shared/baked/creature_token/wolf.png",
    }
    migrated = migrate_manifest(legacy)
    assert migrated["source"] == "procedural"
    assert migrated["license"] == "CC0"


def test_migration_does_not_overwrite_existing_fields():
    """If a manifest already has source set, migration leaves it alone
    even if the path would suggest a different source."""
    manifest = {
        "asset_id": "garth",
        "kind": "portrait",
        "path": "C:/Dev/.shared/baked/packs/synty/fantasy_kingdom/garth.png",
        "source": "ai_2d",  # already set — keep this
        "license": "Scenario_owned",
        "redistribution": True,
    }
    migrated = migrate_manifest(manifest)
    assert migrated["source"] == "ai_2d"  # preserved
    assert migrated["license"] == "Scenario_owned"  # preserved
    assert migrated["redistribution"] is True  # preserved (NOT auto-flipped to False)


def test_migration_is_idempotent():
    legacy = {"asset_id": "x", "kind": "y", "path": "/p"}
    once = migrate_manifest(legacy)
    snapshot = dict(once)
    twice = migrate_manifest(once)
    # The two migrations should produce identical results except possibly
    # for generated_at if it wasn't set originally — but since we set it
    # on the first call, it should be preserved on the second.
    assert twice["source"] == snapshot["source"]
    assert twice["license"] == snapshot["license"]
    assert twice["cost_usd"] == snapshot["cost_usd"]


def test_is_modern_manifest_detects_new_schema():
    legacy = {"asset_id": "x", "kind": "y", "path": "/p"}
    assert is_modern_manifest(legacy) is False

    modern = make_manifest(asset_id="x", kind="y", path="/p")
    assert is_modern_manifest(modern) is True

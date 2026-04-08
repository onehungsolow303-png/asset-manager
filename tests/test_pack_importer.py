"""Tests for the third-party asset pack importer.

Verifies:
  - Walks a directory and registers each recognized asset
  - Skips files with unrecognized extensions
  - Skips hidden directories (.git, .venv, etc.)
  - Idempotent: re-running on the same pack updates in place
  - asset_id_prefix prevents collisions across packs
  - tag_strategy controls how tags are derived
  - kind is inferred from parent directory by default
  - kind_overrides remaps non-standard parent dir names
  - Manifest carries source=pack, pack_name, license, redistribution
  - swap_safe is False for pack assets (hand-curated, never auto-overwrite)
  - Missing local_path is handled gracefully (returns empty result, no crash)
"""
from __future__ import annotations

from pathlib import Path

from asset_manager.library.pack_importer import (
    ImportResult,
    PackSpec,
    import_pack,
)


class FakeCatalog:
    """Minimal Catalog stand-in for tests — same surface as Catalog.add/get."""

    def __init__(self) -> None:
        self.entries: dict[str, dict] = {}

    def add(self, asset_id: str, manifest: dict) -> None:
        manifest = dict(manifest)
        manifest.setdefault("asset_id", asset_id)
        self.entries[asset_id] = manifest

    def get(self, asset_id: str) -> dict | None:
        return self.entries.get(asset_id)


def _make_pack(tmp_path: Path, layout: dict[str, bytes]) -> Path:
    """Build a fake pack directory under tmp_path from a {relpath: bytes} layout."""
    for rel, content in layout.items():
        full = tmp_path / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(content)
    return tmp_path


# ─── Walk + register ───────────────────────────────────────────────

def test_import_walks_pack_and_registers_each_asset(tmp_path):
    pack = _make_pack(tmp_path, {
        "characters/wizard.glb": b"fake glb",
        "characters/knight.glb": b"fake glb",
        "props/torch.glb": b"fake glb",
    })
    catalog = FakeCatalog()
    spec = PackSpec(
        pack_id="testpack",
        pack_name="Test Pack",
        license_code="CC0",
        redistribution=True,
    )

    result = import_pack(catalog, pack, spec)

    assert result.added == 3
    assert result.updated == 0
    assert result.skipped == 0
    assert "wizard" in catalog.entries
    assert "knight" in catalog.entries
    assert "torch" in catalog.entries


def test_import_infers_kind_from_parent_directory(tmp_path):
    pack = _make_pack(tmp_path, {
        "characters/wizard.glb": b"fake",
        "props/torch.glb": b"fake",
    })
    catalog = FakeCatalog()
    spec = PackSpec(
        pack_id="testpack", pack_name="Test", license_code="CC0", redistribution=True,
    )
    import_pack(catalog, pack, spec)

    assert catalog.entries["wizard"]["kind"] == "characters"
    assert catalog.entries["torch"]["kind"] == "props"


def test_kind_overrides_remap_parent_dir_names(tmp_path):
    pack = _make_pack(tmp_path, {
        "Walls/north.glb": b"fake",
        "Floors/wood.glb": b"fake",
    })
    catalog = FakeCatalog()
    spec = PackSpec(
        pack_id="testpack",
        pack_name="Test",
        license_code="CC0",
        redistribution=True,
        kind_overrides={"Walls": "dungeon_wall", "Floors": "dungeon_floor"},
    )
    import_pack(catalog, pack, spec)

    assert catalog.entries["north"]["kind"] == "dungeon_wall"
    assert catalog.entries["wood"]["kind"] == "dungeon_floor"


# ─── Filtering ─────────────────────────────────────────────────────

def test_import_skips_unrecognized_extensions(tmp_path):
    pack = _make_pack(tmp_path, {
        "characters/wizard.glb": b"fake",
        "characters/notes.txt": b"hello",        # not an asset
        "characters/source.blend1": b"backup",   # not recognized
        "characters/icon.png": b"fake png",
    })
    catalog = FakeCatalog()
    spec = PackSpec(
        pack_id="testpack", pack_name="Test", license_code="CC0", redistribution=True,
    )
    import_pack(catalog, pack, spec)

    assert "wizard" in catalog.entries
    assert "icon" in catalog.entries
    assert "notes" not in catalog.entries
    assert "source" not in catalog.entries


def test_import_skips_hidden_directories(tmp_path):
    pack = _make_pack(tmp_path, {
        "characters/wizard.glb": b"fake",
        ".git/objects/whatever.glb": b"hidden",
        ".venv/lib/site-packages/junk.glb": b"hidden",
    })
    catalog = FakeCatalog()
    spec = PackSpec(
        pack_id="testpack", pack_name="Test", license_code="CC0", redistribution=True,
    )
    import_pack(catalog, pack, spec)

    assert "wizard" in catalog.entries
    assert "whatever" not in catalog.entries
    assert "junk" not in catalog.entries


# ─── Idempotency ───────────────────────────────────────────────────

def test_reimporting_same_pack_updates_in_place(tmp_path):
    pack = _make_pack(tmp_path, {
        "characters/wizard.glb": b"fake",
    })
    catalog = FakeCatalog()
    spec = PackSpec(
        pack_id="testpack", pack_name="Test", license_code="CC0", redistribution=True,
    )

    first = import_pack(catalog, pack, spec)
    assert first.added == 1
    assert first.updated == 0

    second = import_pack(catalog, pack, spec)
    assert second.added == 0
    assert second.updated == 1

    assert len(catalog.entries) == 1  # not duplicated


def test_reimport_preserves_original_generated_at(tmp_path):
    pack = _make_pack(tmp_path, {"characters/wizard.glb": b"fake"})
    catalog = FakeCatalog()
    spec = PackSpec(
        pack_id="testpack", pack_name="Test", license_code="CC0", redistribution=True,
    )

    import_pack(catalog, pack, spec)
    original_ts = catalog.entries["wizard"]["generated_at"]

    # Re-import — generated_at should be preserved
    import_pack(catalog, pack, spec)
    assert catalog.entries["wizard"]["generated_at"] == original_ts


# ─── Asset ID prefix ───────────────────────────────────────────────

def test_asset_id_prefix_prevents_collisions(tmp_path):
    pack = _make_pack(tmp_path, {
        "props/wall.glb": b"fake",
    })
    catalog = FakeCatalog()
    spec = PackSpec(
        pack_id="kaykit_dungeon",
        pack_name="KayKit Dungeon",
        license_code="KayKit_free",
        redistribution=True,
        asset_id_prefix="kaykit_dungeon_",
    )
    import_pack(catalog, pack, spec)

    assert "kaykit_dungeon_wall" in catalog.entries
    assert "wall" not in catalog.entries


# ─── Tag strategies ────────────────────────────────────────────────

def test_filename_tag_strategy_splits_on_separators(tmp_path):
    pack = _make_pack(tmp_path, {
        "props/stone_wall_corner_01.glb": b"fake",
    })
    catalog = FakeCatalog()
    spec = PackSpec(
        pack_id="testpack", pack_name="Test", license_code="CC0", redistribution=True,
        tag_strategy="filename",
    )
    import_pack(catalog, pack, spec)

    tags = set(catalog.entries["stone_wall_corner_01"]["tags"])
    assert {"stone", "wall", "corner"}.issubset(tags)
    assert "01" not in tags  # numeric-only stripped


def test_parent_dir_tag_strategy_uses_directory_name(tmp_path):
    pack = _make_pack(tmp_path, {
        "dungeon_walls/corner.glb": b"fake",
    })
    catalog = FakeCatalog()
    spec = PackSpec(
        pack_id="testpack", pack_name="Test", license_code="CC0", redistribution=True,
        tag_strategy="parent_dir",
    )
    import_pack(catalog, pack, spec)

    tags = set(catalog.entries["corner"]["tags"])
    assert "dungeon_walls" in tags


def test_both_tag_strategy_combines_filename_and_parent_dir(tmp_path):
    pack = _make_pack(tmp_path, {
        "dungeon_walls/stone_corner.glb": b"fake",
    })
    catalog = FakeCatalog()
    spec = PackSpec(
        pack_id="testpack", pack_name="Test", license_code="CC0", redistribution=True,
        tag_strategy="both",
    )
    import_pack(catalog, pack, spec)

    tags = set(catalog.entries["stone_corner"]["tags"])
    assert {"stone", "corner", "dungeon_walls"}.issubset(tags)


# ─── Manifest provenance fields ────────────────────────────────────

def test_imported_manifest_carries_full_provenance(tmp_path):
    pack = _make_pack(tmp_path, {"characters/wizard.glb": b"fake"})
    catalog = FakeCatalog()
    spec = PackSpec(
        pack_id="synty_fk",
        pack_name="POLYGON Fantasy Kingdom",
        license_code="Synty_standard",
        redistribution=False,  # Synty is restricted
    )
    import_pack(catalog, pack, spec)

    m = catalog.entries["wizard"]
    assert m["source"] == "pack"
    assert m["pack_name"] == "POLYGON Fantasy Kingdom"
    assert m["license"] == "Synty_standard"
    assert m["redistribution"] is False  # critical for Synty
    assert m["swap_safe"] is False  # pack assets are hand-curated
    assert m["cost_usd"] == 0.0


def test_free_pack_marks_redistribution_true(tmp_path):
    pack = _make_pack(tmp_path, {"characters/wizard.glb": b"fake"})
    catalog = FakeCatalog()
    spec = PackSpec(
        pack_id="kaykit_test",
        pack_name="KayKit Test",
        license_code="KayKit_free",
        redistribution=True,
    )
    import_pack(catalog, pack, spec)

    assert catalog.entries["wizard"]["redistribution"] is True


# ─── Error handling ────────────────────────────────────────────────

def test_missing_pack_root_returns_empty_result(tmp_path):
    catalog = FakeCatalog()
    spec = PackSpec(
        pack_id="nope", pack_name="Nope", license_code="CC0", redistribution=True,
    )
    result = import_pack(catalog, tmp_path / "does_not_exist", spec)

    assert isinstance(result, ImportResult)
    assert result.added == 0
    assert result.updated == 0
    assert len(catalog.entries) == 0


def test_pack_root_that_is_a_file_returns_empty(tmp_path):
    not_a_dir = tmp_path / "thisisafile.txt"
    not_a_dir.write_text("hi")
    catalog = FakeCatalog()
    spec = PackSpec(
        pack_id="bad", pack_name="Bad", license_code="CC0", redistribution=True,
    )
    result = import_pack(catalog, not_a_dir, spec)

    assert result.added == 0
    assert len(catalog.entries) == 0

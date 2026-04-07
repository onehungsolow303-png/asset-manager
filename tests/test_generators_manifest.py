import json
from pathlib import Path

from PIL import Image

from asset_manager.generators.manifest_builder import (
    AssetEntry,
    AssetManifest,
    build_manifest,
    save_manifest,
    to_json,
)


def _write_png(path: Path, size: tuple[int, int] = (4, 4)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (255, 0, 0, 255)).save(path, format="PNG")


def test_empty_directory_returns_empty_manifest(tmp_path: Path):
    manifest = build_manifest(tmp_path)
    assert manifest.assets == []
    assert manifest.version == "1.0.0"
    assert manifest.generator == "AssetManager"
    assert manifest.created_at != ""


def test_nonexistent_directory_returns_empty(tmp_path: Path):
    manifest = build_manifest(tmp_path / "does-not-exist")
    assert manifest.assets == []


def test_single_sprite_classified(tmp_path: Path):
    _write_png(tmp_path / "Sprite_wolf.png")
    manifest = build_manifest(tmp_path)
    assert len(manifest.assets) == 1
    entry = manifest.assets[0]
    assert entry.id == "Sprite_wolf"
    assert entry.category == "sprite"
    assert entry.format == "png"
    assert entry.width == 4
    assert entry.height == 4
    assert entry.tags == ["sprite"]


def test_classification_rules(tmp_path: Path):
    _write_png(tmp_path / "Sprite_wolf.png")
    _write_png(tmp_path / "Tile_grass.png")
    _write_png(tmp_path / "UI_button.png")
    _write_png(tmp_path / "wood_floor.png")
    manifest = build_manifest(tmp_path)
    assert len(manifest.assets) == 4
    by_id = {a.id: a.category for a in manifest.assets}
    assert by_id["Sprite_wolf"] == "sprite"
    assert by_id["Tile_grass"] == "tileset"
    assert by_id["UI_button"] == "ui"
    assert by_id["wood_floor"] == "texture"


def test_save_and_round_trip(tmp_path: Path):
    _write_png(tmp_path / "Sprite_x.png")
    manifest = build_manifest(tmp_path)
    out_path = tmp_path / "manifest.json"
    save_manifest(manifest, out_path)
    assert out_path.exists()
    loaded = json.loads(out_path.read_text())
    assert loaded["version"] == "1.0.0"
    assert loaded["generator"] == "AssetManager"
    assert len(loaded["assets"]) == 1
    assert loaded["assets"][0]["id"] == "Sprite_x"
    assert loaded["assets"][0]["category"] == "sprite"


def test_recursive_scan(tmp_path: Path):
    _write_png(tmp_path / "deep" / "Sprite_a.png")
    _write_png(tmp_path / "deep" / "deeper" / "Tile_b.png")
    manifest = build_manifest(tmp_path)
    assert len(manifest.assets) == 2
    paths = {a.path for a in manifest.assets}
    assert "deep/Sprite_a.png" in paths
    assert "deep/deeper/Tile_b.png" in paths

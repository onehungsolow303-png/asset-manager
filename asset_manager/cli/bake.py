"""Headless asset baking CLI.

Reads a YAML recipe describing a batch of assets to generate, calls each
generator in-process (no HTTP), writes the resulting PNGs under
`C:/Dev/.shared/baked/<kind>/<id>.png`, and prints a per-asset verdict.

Usage:
    python -m asset_manager.cli.bake recipe.yaml
    python -m asset_manager.cli.bake recipe.yaml --root /tmp/test_baked

Recipe format (see `asset_manager/cli/sample_recipe.yaml` for a working
example):

    assets:
      - id: wolf_token
        kind: creature_token
        color: [120, 80, 60, 255]
        size: 32

      - id: forest_terrain
        kind: terrain
        width: 32
        height: 32
        floor_color: [80, 120, 40, 255]
        wall_color:  [50, 80, 20, 255]
        seed: 7

      - id: dagger_icon
        kind: item_icon
        color: [200, 200, 220, 255]
        shape: diamond
        size: 16

      - id: forge_tileset
        kind: tileset
        tile_size: 16
        tiles_per_row: 2
        tile_colors:
          - [120, 80, 40, 255]
          - [80, 50, 20, 255]
          - [180, 100, 40, 255]
          - [60, 30, 10, 255]
        seed: 11

Each entry MUST have `id` and `kind`. Other fields are kind-specific
(see the four `_handle_*` functions in `asset_manager/bridge/server.py`
for the same parameter shapes).

Exit codes:
    0  all assets baked successfully
    1  any failure (file printed which one)
    2  recipe file missing or malformed
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from asset_manager.generators.procedural_sprite import (
    generate_creature_token,
    generate_item_icon,
)
from asset_manager.generators.texture import (
    generate_terrain_texture,
    generate_tileset,
)
from asset_manager.library.storage import Storage


# Reuse the bridge's color helper for [R,G,B,A] -> tuple
def _color(spec: dict[str, Any], key: str, default: list[int]) -> tuple[int, int, int, int]:
    c = spec.get(key, default)
    return (int(c[0]), int(c[1]), int(c[2]), int(c[3]) if len(c) > 3 else 255)


def _bake_creature_token(entry: dict[str, Any], storage: Storage) -> Path:
    color = _color(entry, "color", [255, 255, 255, 255])
    size = int(entry.get("size", 32))
    out = storage.path_for("creature_token", entry["id"], ext="png")
    generate_creature_token(color, size=size, out_path=out)
    return out


def _bake_item_icon(entry: dict[str, Any], storage: Storage) -> Path:
    color = _color(entry, "color", [255, 255, 255, 255])
    size = int(entry.get("size", 16))
    shape = str(entry.get("shape", "square"))
    out = storage.path_for("item_icon", entry["id"], ext="png")
    generate_item_icon(color, shape=shape, size=size, out_path=out)
    return out


def _bake_terrain(entry: dict[str, Any], storage: Storage) -> Path:
    width = int(entry.get("width", 32))
    height = int(entry.get("height", 32))
    floor = _color(entry, "floor_color", [100, 80, 60, 255])
    wall = _color(entry, "wall_color", [50, 40, 30, 255])
    seed = int(entry.get("seed", 42))
    out = storage.path_for("terrain", entry["id"], ext="png")
    generate_terrain_texture(width, height, floor, wall, seed=seed, out_path=out)
    return out


def _bake_tileset(entry: dict[str, Any], storage: Storage) -> Path:
    tile_size = int(entry.get("tile_size", 16))
    tiles_per_row = int(entry.get("tiles_per_row", 4))
    raw = entry.get("tile_colors") or [[100, 0, 0, 255]]
    colors = [
        (int(c[0]), int(c[1]), int(c[2]), int(c[3]) if len(c) > 3 else 255)
        for c in raw
    ]
    seed = int(entry.get("seed", 42))
    out = storage.path_for("tileset", entry["id"], ext="png")
    generate_tileset(tile_size, tiles_per_row, colors, seed=seed, out_path=out)
    return out


_HANDLERS = {
    "creature_token": _bake_creature_token,
    "item_icon": _bake_item_icon,
    "terrain": _bake_terrain,
    "tileset": _bake_tileset,
}


def bake_recipe(recipe_path: Path, root: Path | None = None) -> tuple[int, int]:
    """Run the recipe. Returns (success_count, failure_count)."""
    if not recipe_path.exists():
        print(f"FATAL: recipe file not found: {recipe_path}", file=sys.stderr)
        return 0, -1

    try:
        recipe = yaml.safe_load(recipe_path.read_text())
    except yaml.YAMLError as e:
        print(f"FATAL: recipe YAML parse error: {e}", file=sys.stderr)
        return 0, -1

    if not isinstance(recipe, dict) or "assets" not in recipe:
        print("FATAL: recipe must be a dict with an 'assets' key", file=sys.stderr)
        return 0, -1

    storage = Storage(root=root) if root is not None else Storage()
    success = 0
    failure = 0

    for entry in recipe["assets"]:
        if not isinstance(entry, dict):
            print(f"SKIP: non-dict entry in assets list: {entry!r}", file=sys.stderr)
            failure += 1
            continue
        asset_id = entry.get("id")
        kind = entry.get("kind")
        if not asset_id or not kind:
            print(f"SKIP: entry missing id or kind: {entry!r}", file=sys.stderr)
            failure += 1
            continue
        handler = _HANDLERS.get(kind)
        if handler is None:
            print(
                f"SKIP {asset_id}: unknown kind {kind!r} "
                f"(supported: {sorted(_HANDLERS.keys())})",
                file=sys.stderr,
            )
            failure += 1
            continue

        try:
            out_path = handler(entry, storage)
        except Exception as e:  # boundary
            print(f"FAIL {asset_id} ({kind}): {e}", file=sys.stderr)
            failure += 1
            continue

        print(f"OK   {asset_id} ({kind}) -> {out_path}")
        success += 1

    return success, failure


def main() -> int:
    ap = argparse.ArgumentParser(prog="asset_manager.cli.bake")
    ap.add_argument("recipe", type=Path, help="path to a YAML recipe file")
    ap.add_argument(
        "--root",
        type=Path,
        default=None,
        help="override Storage root (default: C:/Dev/.shared/baked)",
    )
    args = ap.parse_args()

    success, failure = bake_recipe(args.recipe, args.root)
    if failure < 0:
        return 2
    print()
    print(f"baked {success} assets, {failure} failed")
    return 0 if failure == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

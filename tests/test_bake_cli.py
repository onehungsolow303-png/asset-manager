"""Bake CLI tests.

Exercises asset_manager.cli.bake against the sample recipe + a few
synthetic recipes (success path, unknown kind, missing fields, malformed
file). Each test redirects Storage to a tmp_path so it doesn't pollute
C:/Dev/.shared/baked/.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from asset_manager.cli.bake import bake_recipe

GOOD_RECIPE = """
assets:
  - id: wolf
    kind: creature_token
    color: [200, 50, 50, 255]
    size: 32

  - id: little_terrain
    kind: terrain
    width: 8
    height: 8
    floor_color: [80, 120, 40, 255]
    wall_color:  [50, 80, 20, 255]
    seed: 1
"""

UNKNOWN_KIND_RECIPE = """
assets:
  - id: oddity
    kind: phaser_blast
"""

MISSING_FIELD_RECIPE = """
assets:
  - kind: creature_token
    color: [100, 100, 100, 255]
"""

MALFORMED_YAML = "assets: [not a dict and not a list of dicts ::: bad"


def test_recipe_writes_real_pngs(tmp_path: Path):
    recipe_file = tmp_path / "recipe.yaml"
    recipe_file.write_text(GOOD_RECIPE)
    success, failure = bake_recipe(recipe_file, root=tmp_path / "baked")
    assert success == 2
    assert failure == 0

    wolf_png = tmp_path / "baked" / "creature_token" / "wolf.png"
    terrain_png = tmp_path / "baked" / "terrain" / "little_terrain.png"
    assert wolf_png.exists()
    assert terrain_png.exists()

    img = Image.open(wolf_png)
    assert img.size == (32, 32)
    assert img.mode == "RGBA"

    img = Image.open(terrain_png)
    assert img.size == (8, 8)


def test_unknown_kind_counts_as_failure(tmp_path: Path):
    recipe_file = tmp_path / "recipe.yaml"
    recipe_file.write_text(UNKNOWN_KIND_RECIPE)
    success, failure = bake_recipe(recipe_file, root=tmp_path / "baked")
    assert success == 0
    assert failure == 1


def test_missing_id_counts_as_failure(tmp_path: Path):
    recipe_file = tmp_path / "recipe.yaml"
    recipe_file.write_text(MISSING_FIELD_RECIPE)
    success, failure = bake_recipe(recipe_file, root=tmp_path / "baked")
    assert success == 0
    assert failure == 1


def test_missing_recipe_file_returns_minus_one(tmp_path: Path):
    success, failure = bake_recipe(tmp_path / "does-not-exist.yaml")
    assert failure == -1


def test_malformed_yaml_returns_minus_one(tmp_path: Path):
    recipe_file = tmp_path / "recipe.yaml"
    recipe_file.write_text(MALFORMED_YAML)
    success, failure = bake_recipe(recipe_file)
    assert failure == -1


def test_sample_recipe_round_trip(tmp_path: Path):
    """The committed sample_recipe.yaml should bake without errors."""
    sample = Path(__file__).resolve().parent.parent / "asset_manager" / "cli" / "sample_recipe.yaml"
    assert sample.exists(), f"sample recipe missing at {sample}"
    success, failure = bake_recipe(sample, root=tmp_path / "baked")
    assert failure == 0
    assert success == 7

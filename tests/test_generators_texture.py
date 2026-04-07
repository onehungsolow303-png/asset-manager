import hashlib

from PIL import Image

from asset_manager.generators.texture import generate_terrain_texture, generate_tileset


def test_terrain_dimensions():
    img = generate_terrain_texture(8, 8, (100, 80, 60, 255), (50, 40, 30, 255), seed=42)
    assert img.size == (8, 8)
    assert img.mode == "RGBA"


def test_terrain_deterministic_under_same_seed():
    img1 = generate_terrain_texture(8, 8, (100, 80, 60, 255), (50, 40, 30, 255), seed=42)
    img2 = generate_terrain_texture(8, 8, (100, 80, 60, 255), (50, 40, 30, 255), seed=42)
    assert _hash(img1) == _hash(img2)


def test_terrain_different_seeds_produce_different_output():
    img1 = generate_terrain_texture(8, 8, (100, 80, 60, 255), (50, 40, 30, 255), seed=42)
    img2 = generate_terrain_texture(8, 8, (100, 80, 60, 255), (50, 40, 30, 255), seed=99)
    assert _hash(img1) != _hash(img2)


def test_tileset_dimensions():
    colors = [
        (100, 0, 0, 255),
        (0, 100, 0, 255),
        (0, 0, 100, 255),
        (100, 100, 0, 255),
    ]
    img = generate_tileset(tile_size=16, tiles_per_row=4, tile_colors=colors, seed=42)
    assert img.size == (64, 16)
    assert img.mode == "RGBA"


def test_tileset_writes_to_disk(tmp_path):
    colors = [(100, 0, 0, 255)]
    out = tmp_path / "sub" / "tileset.png"
    img = generate_tileset(tile_size=8, tiles_per_row=1, tile_colors=colors, out_path=out)
    assert out.exists()
    reloaded = Image.open(out)
    assert reloaded.size == img.size


def _hash(img: Image.Image) -> str:
    return hashlib.sha256(img.tobytes()).hexdigest()

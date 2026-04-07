from pathlib import Path

import pytest
from PIL import Image

from asset_manager.generators.procedural_sprite import (
    generate_creature_token,
    generate_item_icon,
)


def test_creature_token_dimensions():
    img = generate_creature_token((200, 50, 50, 255), size=32)
    assert img.size == (32, 32)
    assert img.mode == "RGBA"


def test_creature_token_center_is_base_color():
    img = generate_creature_token((200, 50, 50, 255), size=32)
    assert img.getpixel((16, 16)) == (200, 50, 50, 255)


def test_creature_token_corner_is_transparent():
    img = generate_creature_token((200, 50, 50, 255), size=32)
    assert img.getpixel((0, 0)) == (0, 0, 0, 0)


def test_creature_token_rim_is_darker_than_base():
    # At size=32, center=16, radius=14 (=16-2). The rim band is the
    # half-open ring 13 <= dist < 14. Pixel (16, 3) has dist=13 exactly
    # and is the topmost rim pixel along the vertical axis.
    img = generate_creature_token((200, 50, 50, 255), size=32)
    rim = img.getpixel((16, 3))
    base = (200, 50, 50, 255)
    assert rim != (0, 0, 0, 0), "rim should not be transparent"
    assert rim[0] < base[0], f"rim red {rim[0]} should be darker than base {base[0]}"


def test_item_icon_square_has_transparent_border():
    img = generate_item_icon((100, 200, 100, 255), shape="square", size=16)
    assert img.getpixel((0, 0)) == (0, 0, 0, 0)
    assert img.getpixel((1, 1)) == (0, 0, 0, 0)
    assert img.getpixel((8, 8)) == (100, 200, 100, 255)


def test_item_icon_circle_center_filled():
    img = generate_item_icon((100, 200, 100, 255), shape="circle", size=16)
    assert img.getpixel((8, 8)) == (100, 200, 100, 255)
    assert img.getpixel((0, 0)) == (0, 0, 0, 0)


def test_item_icon_diamond_center_filled():
    img = generate_item_icon((100, 200, 100, 255), shape="diamond", size=16)
    assert img.getpixel((8, 8)) == (100, 200, 100, 255)
    assert img.getpixel((0, 0)) == (0, 0, 0, 0)
    assert img.getpixel((15, 15)) == (0, 0, 0, 0)


def test_creature_token_writes_to_disk(tmp_path: Path):
    out = tmp_path / "subdir" / "token.png"
    img = generate_creature_token((200, 50, 50, 255), size=32, out_path=out)
    assert out.exists()
    reloaded = Image.open(out)
    assert reloaded.size == img.size
    assert reloaded.mode == "RGBA"

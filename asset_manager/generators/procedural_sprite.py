"""ProceduralSpriteGenerator - Python port of the archived
ForeverEngine.AssetGeneration.ProceduralSpriteGenerator.cs.

Generates pixel-art sprites for the asset library. Pillow-backed; nearest-neighbor
filtering is implicit because we manipulate pixels directly. Output is RGBA PNG.

C# reference: C:/Dev/_archive/forever-engine-pre-pivot/Assets/Scripts/AssetGeneration/AssetGeneration/ProceduralSpriteGenerator.cs
Spec: 2026-04-06-csharp-to-python-assetgen-port-design.md §5.1
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from PIL import Image


def generate_creature_token(
    base_color: tuple[int, int, int, int],
    size: int = 32,
    out_path: Optional[Path] = None,
) -> Image.Image:
    """Filled-circle creature token with a single-pixel rim half as bright as base.

    Mirrors C# GenerateCreatureToken: clear background, center disc filled with
    base_color, single-pixel rim is base_color blended with black at 0.5.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = img.load()
    center = size / 2.0
    radius = size / 2.0 - 2.0
    rim_color = _lerp_color(base_color, (0, 0, 0, base_color[3]), 0.5)
    for y in range(size):
        for x in range(size):
            dist = math.sqrt((x - center) ** 2 + (y - center) ** 2)
            if dist < radius - 1:
                pixels[x, y] = base_color
            elif dist < radius:
                pixels[x, y] = rim_color
            # else stays transparent
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, format="PNG")
    return img


def generate_item_icon(
    color: tuple[int, int, int, int],
    shape: str = "square",
    size: int = 16,
    out_path: Optional[Path] = None,
) -> Image.Image:
    """Item icon in one of three shapes: square (default), circle, diamond.

    Mirrors C# GenerateItemIcon: shape filled with color, no rim, transparent
    background. The 'square' shape inscribes a 1-pixel transparent border on
    all sides (matches the C# `x > 1 && x < size-2` check).
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = img.load()
    center = size / 2.0
    for y in range(size):
        for x in range(size):
            if shape == "circle":
                inside = math.sqrt((x - center) ** 2 + (y - center) ** 2) < center - 1
            elif shape == "diamond":
                inside = abs(x - center) + abs(y - center) < center - 1
            else:  # square (default)
                inside = 1 < x < size - 2 and 1 < y < size - 2
            if inside:
                pixels[x, y] = color
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, format="PNG")
    return img


def _lerp_color(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
    t: float,
) -> tuple[int, int, int, int]:
    """Linear interpolation between two RGBA colors. Mirrors Unity Color.Lerp."""
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
        round(a[3] + (b[3] - a[3]) * t),
    )

"""TextureGenerator - Python port of the archived
ForeverEngine.AssetGeneration.TextureGenerator.cs.

Generates Perlin-blended terrain textures and color-varied tilesets. Output
is RGBA PNG. Determinism is preserved via _perlin.seed(seed).

C# reference: C:/Dev/_archive/forever-engine-pre-pivot/Assets/Scripts/AssetGeneration/AssetGeneration/TextureGenerator.cs
Spec: 2026-04-06-csharp-to-python-assetgen-port-design.md §5.2
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image

from . import _perlin


def generate_terrain_texture(
    width: int,
    height: int,
    floor_color: tuple[int, int, int, int],
    wall_color: tuple[int, int, int, int],
    seed: int = 42,
    out_path: Optional[Path] = None,
) -> Image.Image:
    """Perlin-blended terrain. Mirrors C# GenerateTerrainTexture."""
    _perlin.seed(seed)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = img.load()
    for y in range(height):
        for x in range(width):
            n = _perlin.octave(x * 0.1, y * 0.1, 3)
            # Map noise from [-1, 1] to [0, 1] for the lerp
            t = (n + 1.0) * 0.5
            base = _lerp_color(floor_color, wall_color, t)
            variation = _perlin.sample(x * 0.5, y * 0.5) * 0.1 - 0.05
            r = _clamp01(base[0] / 255.0 + variation)
            g = _clamp01(base[1] / 255.0 + variation)
            b = _clamp01(base[2] / 255.0 + variation)
            pixels[x, y] = (round(r * 255), round(g * 255), round(b * 255), base[3])
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, format="PNG")
    return img


def generate_tileset(
    tile_size: int,
    tiles_per_row: int,
    tile_colors: list[tuple[int, int, int, int]],
    seed: int = 42,
    out_path: Optional[Path] = None,
) -> Image.Image:
    """Grid of single-color tiles with subtle Perlin variation.
    Mirrors C# GenerateTileset."""
    total_tiles = len(tile_colors)
    rows = (total_tiles + tiles_per_row - 1) // tiles_per_row
    w = tile_size * tiles_per_row
    h = tile_size * rows
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pixels = img.load()
    _perlin.seed(seed)
    for t in range(total_tiles):
        col = t % tiles_per_row
        row = t // tiles_per_row
        ox = col * tile_size
        oy = row * tile_size
        base = tile_colors[t]
        for y in range(tile_size):
            for x in range(tile_size):
                n = _perlin.sample((ox + x) * 0.3, (oy + y) * 0.3) * 0.15 - 0.075
                r = _clamp01(base[0] / 255.0 + n)
                g = _clamp01(base[1] / 255.0 + n)
                b = _clamp01(base[2] / 255.0 + n)
                pixels[ox + x, oy + y] = (
                    round(r * 255),
                    round(g * 255),
                    round(b * 255),
                    base[3],
                )
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, format="PNG")
    return img


def _lerp_color(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
    t: float,
) -> tuple[int, int, int, int]:
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
        round(a[3] + (b[3] - a[3]) * t),
    )


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))

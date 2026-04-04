"""
TerrainAgent — Generates base elevation and moisture maps using noise algorithms.
Supports multiple biome presets and terrain generation algorithms.
"""

import numpy as np
from base_agent import BaseAgent
from shared_state import SharedState
from typing import Any
import math


def perlin_noise_2d(shape, scale, seed, octaves=6, persistence=0.5, lacunarity=2.0):
    """
    Generate 2D Perlin-like noise using numpy (gradient noise approximation).
    Uses multiple octaves of simplex-style value noise for organic results.
    """
    rng = np.random.default_rng(seed)
    h, w = shape
    noise = np.zeros((h, w), dtype=np.float32)

    for octave in range(octaves):
        freq = lacunarity ** octave
        amp = persistence ** octave
        # Generate random gradients at grid scale
        grid_h = max(2, int(h / (scale / freq)))
        grid_w = max(2, int(w / (scale / freq)))
        gradients = rng.random((grid_h + 1, grid_w + 1)).astype(np.float32)

        # Interpolate to full resolution
        y_coords = np.linspace(0, grid_h - 1, h)
        x_coords = np.linspace(0, grid_w - 1, w)
        y_grid, x_grid = np.meshgrid(y_coords, x_coords, indexing='ij')

        # Bilinear interpolation of gradients
        y0 = np.floor(y_grid).astype(int)
        x0 = np.floor(x_grid).astype(int)
        y1 = np.minimum(y0 + 1, grid_h)
        x1 = np.minimum(x0 + 1, grid_w)
        fy = y_grid - y0
        fx = x_grid - x0

        # Smoothstep
        fy = fy * fy * (3 - 2 * fy)
        fx = fx * fx * (3 - 2 * fx)

        top = gradients[y0, x0] * (1 - fx) + gradients[y0, x1] * fx
        bot = gradients[y1, x0] * (1 - fx) + gradients[y1, x1] * fx
        octave_noise = top * (1 - fy) + bot * fy

        noise += octave_noise * amp

    # Normalize to 0–1
    noise = (noise - noise.min()) / (noise.max() - noise.min() + 1e-8)
    return noise


# Biome presets: defines how terrain parameters map to biome characteristics
BIOME_PRESETS = {
    "forest": {
        "elevation_scale": 80, "elevation_octaves": 6,
        "moisture_scale": 60, "moisture_base": 0.5,
        "walkability_threshold": 0.85,
    },
    "mountain": {
        "elevation_scale": 40, "elevation_octaves": 8,
        "moisture_scale": 80, "moisture_base": 0.3,
        "walkability_threshold": 0.7,
    },
    "desert": {
        "elevation_scale": 120, "elevation_octaves": 4,
        "moisture_scale": 100, "moisture_base": 0.1,
        "walkability_threshold": 0.95,
    },
    "swamp": {
        "elevation_scale": 150, "elevation_octaves": 5,
        "moisture_scale": 40, "moisture_base": 0.8,
        "walkability_threshold": 0.6,
    },
    "plains": {
        "elevation_scale": 200, "elevation_octaves": 3,
        "moisture_scale": 80, "moisture_base": 0.4,
        "walkability_threshold": 0.95,
    },
    "tundra": {
        "elevation_scale": 100, "elevation_octaves": 5,
        "moisture_scale": 90, "moisture_base": 0.2,
        "walkability_threshold": 0.8,
    },
    "volcanic": {
        "elevation_scale": 30, "elevation_octaves": 7,
        "moisture_scale": 100, "moisture_base": 0.05,
        "walkability_threshold": 0.6,
    },
    "cave": {
        "elevation_scale": 20, "elevation_octaves": 4,
        "moisture_scale": 50, "moisture_base": 0.6,
        "walkability_threshold": 0.5,
    },
    "dungeon": {
        "elevation_scale": 200, "elevation_octaves": 1,
        "moisture_scale": 200, "moisture_base": 0.3,
        "walkability_threshold": 0.5,
    },
}

# Color palettes for each biome
BIOME_COLORS = {
    "forest": {
        "low": (34, 85, 34),      # dark forest green
        "mid": (50, 120, 50),     # medium green
        "high": (139, 137, 112),  # rocky gray-green
        "peak": (180, 170, 160),  # light stone
    },
    "mountain": {
        "low": (80, 120, 60),
        "mid": (130, 130, 110),
        "high": (170, 165, 155),
        "peak": (240, 240, 245),  # snow
    },
    "desert": {
        "low": (194, 170, 120),
        "mid": (210, 190, 140),
        "high": (180, 150, 100),
        "peak": (160, 130, 80),
    },
    "swamp": {
        "low": (50, 70, 40),
        "mid": (60, 85, 50),
        "high": (70, 90, 55),
        "peak": (90, 100, 70),
    },
    "plains": {
        "low": (100, 150, 60),
        "mid": (120, 170, 70),
        "high": (140, 160, 80),
        "peak": (160, 155, 100),
    },
    "tundra": {
        "low": (180, 200, 210),
        "mid": (200, 215, 225),
        "high": (220, 230, 235),
        "peak": (245, 248, 250),
    },
    "volcanic": {
        "low": (40, 30, 30),
        "mid": (70, 50, 40),
        "high": (100, 60, 30),
        "peak": (180, 80, 20),  # lava glow
    },
    "cave": {
        "low": (30, 28, 25),
        "mid": (55, 50, 45),
        "high": (80, 75, 65),
        "peak": (100, 95, 85),
    },
    "dungeon": {
        "low": (40, 38, 35),
        "mid": (60, 58, 52),
        "high": (80, 76, 68),
        "peak": (100, 95, 88),
    },
}


def generate_terrain_colors(elevation: np.ndarray, moisture: np.ndarray,
                            biome: str) -> np.ndarray:
    """Map elevation + moisture to RGB colors based on biome palette."""
    h, w = elevation.shape
    colors = np.zeros((h, w, 3), dtype=np.uint8)
    palette = BIOME_COLORS.get(biome, BIOME_COLORS["forest"])

    for y in range(h):
        for x in range(w):
            e = elevation[y, x]
            m = moisture[y, x]
            if e < 0.3:
                c = palette["low"]
            elif e < 0.55:
                c = palette["mid"]
            elif e < 0.8:
                c = palette["high"]
            else:
                c = palette["peak"]

            # Moisture shifts green channel slightly
            r, g, b = c
            g = min(255, int(g * (0.85 + 0.3 * m)))
            colors[y, x] = (r, g, b)

    return colors


class TerrainAgent(BaseAgent):
    name = "TerrainAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        biome = params.get("biome", shared_state.config.biome)
        preset = BIOME_PRESETS.get(biome, BIOME_PRESETS["forest"])
        seed = shared_state.config.seed
        h, w = shared_state.config.height, shared_state.config.width

        # Generate elevation
        shared_state.elevation = perlin_noise_2d(
            (h, w),
            scale=preset["elevation_scale"],
            seed=seed,
            octaves=preset["elevation_octaves"],
        )

        # Generate moisture
        shared_state.moisture = perlin_noise_2d(
            (h, w),
            scale=preset["moisture_scale"],
            seed=seed + 1000,
            octaves=4,
        )
        # Shift moisture by biome base
        shared_state.moisture = np.clip(
            shared_state.moisture * 0.5 + preset["moisture_base"] * 0.5, 0, 1
        )

        # Walkability: steep terrain is unwalkable
        gradient_y = np.abs(np.diff(shared_state.elevation, axis=0, prepend=0))
        gradient_x = np.abs(np.diff(shared_state.elevation, axis=1, prepend=0))
        steepness = np.sqrt(gradient_y**2 + gradient_x**2)
        steepness_threshold = 1.0 - preset["walkability_threshold"]
        shared_state.walkability = steepness < steepness_threshold

        # For dungeon/cave: use cellular automata to carve spaces
        if biome in ("cave", "dungeon"):
            shared_state = self._cellular_automata_carve(shared_state, seed)

        # Generate base terrain colors
        shared_state.terrain_color = generate_terrain_colors(
            shared_state.elevation, shared_state.moisture, biome
        )

        return {
            "biome": biome,
            "elevation_range": (float(shared_state.elevation.min()),
                                float(shared_state.elevation.max())),
            "walkable_pct": float(shared_state.walkability.mean() * 100),
        }

    def _cellular_automata_carve(self, state: SharedState, seed: int) -> SharedState:
        """Use cellular automata to create cave/dungeon-like open spaces."""
        rng = np.random.default_rng(seed + 500)
        h, w = state.config.height, state.config.width

        # Start with random fill (~45% walls)
        grid = rng.random((h, w)) < 0.45

        # Run automata iterations
        for _ in range(5):
            new_grid = grid.copy()
            for y in range(1, h - 1):
                for x in range(1, w - 1):
                    neighbors = grid[y-1:y+2, x-1:x+2].sum() - grid[y, x]
                    if grid[y, x]:
                        new_grid[y, x] = neighbors >= 4
                    else:
                        new_grid[y, x] = neighbors >= 5
            grid = new_grid

        # Walls on edges
        grid[0, :] = True
        grid[-1, :] = True
        grid[:, 0] = True
        grid[:, -1] = True

        # Carve: where grid is False = open space (walkable)
        state.walkability = ~grid
        # Darken walls in terrain color
        state.elevation = np.where(grid, 0.9, 0.2)

        return state

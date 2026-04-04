"""
AssetAgent — Scatters environmental objects (trees, rocks, bushes, props).
Uses Poisson disk sampling for natural distribution.
"""

import numpy as np
from base_agent import BaseAgent
from shared_state import SharedState, Entity
from typing import Any


# Asset palettes per biome
ASSET_PALETTES = {
    "forest": [
        ("tree", (25, 80, 25), 3, 0.4),     # (type, color, radius, frequency)
        ("tree", (30, 90, 30), 4, 0.3),
        ("bush", (35, 70, 20), 2, 0.15),
        ("rock", (120, 115, 105), 2, 0.1),
        ("flower", (180, 50, 80), 1, 0.05),
    ],
    "mountain": [
        ("rock", (140, 135, 125), 3, 0.35),
        ("boulder", (110, 105, 95), 5, 0.15),
        ("tree", (40, 80, 40), 3, 0.2),
        ("pine", (20, 60, 25), 3, 0.2),
        ("snow_patch", (230, 235, 240), 4, 0.1),
    ],
    "desert": [
        ("cactus", (50, 100, 40), 2, 0.1),
        ("rock", (160, 140, 110), 3, 0.15),
        ("dead_tree", (100, 80, 50), 2, 0.05),
        ("sand_dune", (200, 180, 140), 6, 0.1),
        ("skull", (200, 195, 180), 1, 0.02),
    ],
    "swamp": [
        ("dead_tree", (60, 55, 40), 3, 0.2),
        ("mushroom", (140, 60, 60), 1, 0.1),
        ("moss_rock", (70, 90, 60), 2, 0.15),
        ("vine", (40, 70, 30), 1, 0.1),
        ("lily_pad", (50, 110, 50), 2, 0.1),
    ],
    "plains": [
        ("grass_tuft", (90, 150, 50), 2, 0.3),
        ("flower", (200, 180, 50), 1, 0.15),
        ("rock", (130, 125, 115), 2, 0.05),
        ("bush", (60, 110, 40), 2, 0.1),
    ],
    "tundra": [
        ("snow_rock", (190, 195, 200), 3, 0.15),
        ("ice_crystal", (150, 200, 230), 2, 0.1),
        ("dead_bush", (120, 110, 90), 2, 0.05),
        ("snow_drift", (220, 225, 230), 5, 0.15),
    ],
    "volcanic": [
        ("lava_rock", (60, 40, 30), 3, 0.2),
        ("obsidian", (20, 18, 15), 2, 0.1),
        ("ember", (200, 80, 20), 1, 0.05),
        ("ash_pile", (70, 65, 60), 4, 0.15),
        ("crystal", (180, 60, 40), 2, 0.05),
    ],
    "cave": [
        ("stalactite", (100, 95, 85), 2, 0.2),
        ("crystal", (80, 140, 180), 2, 0.08),
        ("mushroom", (120, 70, 120), 2, 0.1),
        ("rock_pile", (80, 75, 65), 3, 0.15),
        ("bone", (180, 175, 165), 1, 0.03),
    ],
    "dungeon": [
        ("barrel", (110, 80, 50), 2, 0.1),
        ("chest", (150, 120, 40), 2, 0.03),
        ("torch", (200, 150, 40), 1, 0.08),
        ("bones", (180, 175, 165), 1, 0.05),
        ("cobweb", (180, 180, 180), 2, 0.05),
        ("crate", (120, 90, 55), 2, 0.08),
    ],
    "crash_site": [
        ("debris", (90, 85, 78), 3, 0.25),
        ("metal_shard", (140, 140, 145), 2, 0.15),
        ("scorch_mark", (40, 35, 30), 4, 0.1),
        ("cargo", (120, 100, 60), 2, 0.08),
        ("smoke", (130, 130, 135), 3, 0.05),
        ("glass_shard", (170, 190, 200), 1, 0.05),
    ],
    "treasure_room": [
        ("gold_pile", (200, 170, 40), 2, 0.15),
        ("gem", (100, 50, 150), 1, 0.1),
        ("chest", (150, 120, 40), 2, 0.08),
        ("coin_scatter", (190, 165, 50), 1, 0.12),
        ("goblet", (180, 155, 45), 1, 0.06),
        ("tapestry", (120, 40, 40), 2, 0.04),
    ],
    "mine": [
        ("rail_track", (100, 90, 70), 2, 0.12),
        ("support_beam", (110, 85, 50), 2, 0.15),
        ("cart", (95, 80, 55), 3, 0.04),
        ("pickaxe", (120, 110, 100), 1, 0.05),
        ("ore_chunk", (140, 120, 40), 2, 0.08),
        ("lantern", (200, 160, 50), 1, 0.06),
    ],
    "castle": [
        ("banner", (150, 30, 30), 1, 0.06),
        ("suit_of_armor", (140, 140, 145), 2, 0.04),
        ("torch", (200, 150, 40), 1, 0.1),
        ("barrel", (110, 80, 50), 2, 0.06),
        ("crate", (120, 90, 55), 2, 0.05),
        ("shield", (120, 100, 80), 1, 0.03),
    ],
    "fort": [
        ("weapon_rack", (100, 85, 60), 2, 0.06),
        ("barrel", (110, 80, 50), 2, 0.08),
        ("crate", (120, 90, 55), 2, 0.08),
        ("torch", (200, 150, 40), 1, 0.06),
        ("fence_post", (90, 70, 40), 1, 0.1),
        ("hay_bale", (180, 160, 80), 3, 0.05),
    ],
    "tower": [
        ("bookshelf", (80, 60, 40), 2, 0.06),
        ("potion", (60, 140, 80), 1, 0.05),
        ("crystal_ball", (120, 160, 200), 1, 0.03),
        ("torch", (200, 150, 40), 1, 0.08),
        ("scroll", (200, 190, 150), 1, 0.05),
        ("candle", (200, 180, 100), 1, 0.06),
    ],
    "arena": [
        ("weapon_rack", (100, 85, 60), 2, 0.04),
        ("bones", (180, 175, 165), 1, 0.06),
        ("blood_stain", (120, 20, 20), 2, 0.03),
        ("banner", (150, 30, 30), 1, 0.04),
        ("torch", (200, 150, 40), 1, 0.06),
    ],
    "maze": [
        ("torch", (200, 150, 40), 1, 0.04),
        ("cobweb", (180, 180, 180), 2, 0.05),
        ("bones", (180, 175, 165), 1, 0.03),
        ("vine", (40, 70, 30), 1, 0.04),
        ("marking", (200, 200, 50), 1, 0.02),
    ],
    "rest_area": [
        ("log", (90, 70, 40), 3, 0.08),
        ("bedroll", (120, 80, 60), 2, 0.06),
        ("cooking_pot", (80, 80, 85), 2, 0.03),
        ("pack", (100, 80, 50), 1, 0.05),
        ("embers", (200, 100, 30), 1, 0.04),
    ],
    "crypt": [
        ("sarcophagus", (80, 75, 65), 3, 0.06),
        ("bones", (180, 175, 165), 1, 0.08),
        ("cobweb", (180, 180, 180), 2, 0.06),
        ("candle", (200, 180, 100), 1, 0.05),
        ("urn", (100, 85, 60), 1, 0.04),
        ("skull", (190, 185, 175), 1, 0.03),
    ],
    "tomb": [
        ("sarcophagus", (80, 75, 65), 3, 0.05),
        ("offering", (180, 160, 50), 1, 0.04),
        ("hieroglyph", (140, 120, 80), 1, 0.06),
        ("torch", (200, 150, 40), 1, 0.05),
        ("dust_pile", (120, 110, 95), 2, 0.08),
        ("trap_plate", (100, 95, 85), 1, 0.03),
    ],
    "graveyard": [
        ("dead_tree", (60, 55, 40), 3, 0.1),
        ("headstone", (160, 155, 145), 2, 0.08),
        ("flower", (150, 60, 80), 1, 0.06),
        ("lantern", (200, 160, 50), 1, 0.03),
        ("crow", (20, 20, 25), 1, 0.02),
        ("moss_patch", (60, 80, 50), 2, 0.05),
    ],
    "dock": [
        ("barrel", (110, 80, 50), 2, 0.1),
        ("crate", (120, 90, 55), 2, 0.12),
        ("rope_coil", (140, 120, 80), 1, 0.06),
        ("anchor", (90, 85, 80), 2, 0.03),
        ("fishing_net", (130, 120, 100), 2, 0.04),
        ("lantern", (200, 160, 50), 1, 0.05),
    ],
    "factory": [
        ("gear", (110, 108, 105), 2, 0.08),
        ("pipe", (95, 90, 85), 2, 0.1),
        ("crate", (120, 90, 55), 2, 0.06),
        ("barrel", (110, 80, 50), 2, 0.05),
        ("smoke_stack", (80, 78, 75), 3, 0.03),
        ("anvil", (70, 68, 65), 2, 0.04),
    ],
    "shop": [
        ("barrel", (110, 80, 50), 2, 0.08),
        ("sign", (120, 100, 60), 1, 0.05),
        ("crate", (120, 90, 55), 2, 0.06),
        ("lantern", (200, 160, 50), 1, 0.04),
    ],
    "shopping_center": [
        ("sign", (120, 100, 60), 1, 0.06),
        ("barrel", (110, 80, 50), 2, 0.05),
        ("crate", (120, 90, 55), 2, 0.05),
        ("flower_pot", (140, 80, 80), 1, 0.04),
        ("lantern", (200, 160, 50), 1, 0.06),
        ("bench", (100, 75, 45), 2, 0.04),
    ],
    "temple": [
        ("incense", (160, 140, 100), 1, 0.04),
        ("candle", (200, 180, 100), 1, 0.06),
        ("offering_bowl", (140, 120, 60), 1, 0.03),
        ("banner", (150, 30, 30), 1, 0.04),
        ("statue", (130, 125, 115), 2, 0.03),
        ("flower", (180, 50, 80), 1, 0.04),
    ],
    "church": [
        ("candle", (200, 180, 100), 1, 0.08),
        ("cross", (140, 135, 125), 1, 0.03),
        ("flower", (180, 50, 80), 1, 0.05),
        ("book", (100, 70, 40), 1, 0.04),
        ("banner", (120, 30, 30), 1, 0.03),
    ],
    "biomes": [
        ("oak_tree", (40, 100, 40), 4, 0.12),
        ("pine_tree", (25, 80, 30), 3, 0.10),
        ("palm_tree", (60, 120, 50), 4, 0.04),
        ("cactus", (50, 110, 45), 2, 0.03),
        ("boulder", (120, 115, 100), 3, 0.06),
        ("flower_patch", (180, 80, 120), 2, 0.05),
        ("mushroom", (160, 80, 60), 1, 0.03),
        ("ice_crystal", (180, 210, 230), 2, 0.02),
    ],
}


def poisson_disk_sampling(width: int, height: int, radius: float,
                           mask: np.ndarray, rng: np.random.Generator,
                           max_points: int = 5000) -> list[tuple[int, int]]:
    """
    Poisson disk sampling for natural-looking point distribution.
    Only places points where mask is True.
    """
    cell_size = radius / np.sqrt(2)
    grid_w = int(np.ceil(width / cell_size))
    grid_h = int(np.ceil(height / cell_size))
    grid = [[None for _ in range(grid_w)] for _ in range(grid_h)]

    points = []
    active = []

    # Find a valid starting point
    for _ in range(100):
        sx, sy = rng.integers(0, width), rng.integers(0, height)
        if mask[sy, sx]:
            break
    else:
        return []

    points.append((sx, sy))
    active.append((sx, sy))
    gx, gy = int(sx / cell_size), int(sy / cell_size)
    if 0 <= gy < grid_h and 0 <= gx < grid_w:
        grid[gy][gx] = 0

    k = 30  # attempts per point

    while active and len(points) < max_points:
        idx = rng.integers(len(active))
        px, py = active[idx]
        found = False

        for _ in range(k):
            angle = rng.random() * 2 * np.pi
            dist = radius + rng.random() * radius
            nx = int(px + dist * np.cos(angle))
            ny = int(py + dist * np.sin(angle))

            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if not mask[ny, nx]:
                continue

            gx, gy = int(nx / cell_size), int(ny / cell_size)

            # Check neighbors
            too_close = False
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    cgx, cgy = gx + dx, gy + dy
                    if 0 <= cgx < grid_w and 0 <= cgy < grid_h:
                        if grid[cgy][cgx] is not None:
                            pidx = grid[cgy][cgx]
                            ox, oy = points[pidx]
                            if (nx - ox)**2 + (ny - oy)**2 < radius**2:
                                too_close = True
                                break
                    if too_close:
                        break
                if too_close:
                    break

            if not too_close:
                grid[gy][gx] = len(points)
                points.append((nx, ny))
                active.append((nx, ny))
                found = True
                break

        if not found:
            active.pop(idx)

    return points


class AssetAgent(BaseAgent):
    name = "AssetAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        biome = params.get("theme", shared_state.config.biome)
        density = params.get("density", "medium")

        density_mult = {"low": 0.5, "medium": 1.0, "high": 1.5}
        mult = density_mult.get(density, 1.0)

        palette = ASSET_PALETTES.get(biome, ASSET_PALETTES["forest"])
        h, w = shared_state.config.height, shared_state.config.width
        rng = np.random.default_rng(shared_state.config.seed + 700)

        # Valid placement mask: walkable, no water, no structures
        valid_mask = shared_state.get_walkable_positions()

        total_placed = 0

        for asset_type, color, base_radius, frequency in palette:
            # Adjust radius and count by density and map size
            radius = max(3, int(base_radius * (w / 512) * 3 / mult))
            max_points = int(frequency * w * h / (radius * radius) * mult)

            positions = poisson_disk_sampling(w, h, radius, valid_mask, rng, max_points)

            for px, py in positions:
                # Draw the asset as a small colored shape
                r = max(1, base_radius * w // 512)
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        nx, ny = px + dx, py + dy
                        if (0 <= nx < w and 0 <= ny < h
                            and dx*dx + dy*dy <= r*r
                            and valid_mask[ny, nx]):
                            # Slight color variation
                            cr, cg, cb = color
                            variation = rng.integers(-10, 11)
                            shared_state.terrain_color[ny, nx] = (
                                max(0, min(255, cr + variation)),
                                max(0, min(255, cg + variation)),
                                max(0, min(255, cb + variation)),
                            )

                shared_state.entities.append(Entity(
                    entity_type=asset_type,
                    position=(px, py),
                    size=(r * 2, r * 2),
                    variant=f"{biome}_{asset_type}",
                ))
                total_placed += 1

        return {
            "assets_placed": total_placed,
            "biome": biome,
            "density": density,
        }

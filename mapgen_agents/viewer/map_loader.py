"""Load layered map data from JSON + PNGs for the pygame viewer."""

import json
import os
import numpy as np
from dataclasses import dataclass, field
from PIL import Image


@dataclass
class GameMap:
    """Loaded map data ready for the viewer."""
    width: int
    height: int
    config: dict
    terrain_images: dict = field(default_factory=dict)    # z -> PIL.Image
    terrain_surfaces: dict = field(default_factory=dict)  # z -> pygame Surface (set later by renderer)
    walkability: dict = field(default_factory=dict)        # z -> np.bool array
    entities: dict = field(default_factory=dict)           # z -> list of entity dicts
    transitions: list = field(default_factory=list)
    spawns: list = field(default_factory=list)
    labels: list = field(default_factory=list)

    @property
    def z_levels(self) -> list[int]:
        return sorted(self.terrain_images.keys())


def load_map(map_dir: str) -> GameMap:
    """Load a map from a directory containing map_data.json and z_*.png files."""
    json_path = os.path.join(map_dir, "map_data.json")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cfg = data["config"]
    w, h = cfg["width"], cfg["height"]
    game_map = GameMap(width=w, height=h, config=cfg)

    for zl_data in data.get("z_levels", []):
        z = zl_data["z"]
        png_path = os.path.join(map_dir, zl_data["terrain_png"])
        if os.path.exists(png_path):
            game_map.terrain_images[z] = Image.open(png_path).convert("RGB")

        walk_flat = zl_data.get("walkability", [])
        if walk_flat:
            walk_arr = np.array(walk_flat, dtype=bool).reshape((h, w))
        else:
            walk_arr = np.ones((h, w), dtype=bool)
        game_map.walkability[z] = walk_arr
        game_map.entities[z] = zl_data.get("entities", [])

    game_map.transitions = data.get("transitions", [])
    game_map.spawns = data.get("spawns", [])
    game_map.labels = data.get("labels", [])

    for z in game_map.terrain_images:
        game_map.terrain_surfaces[z] = None  # populated by renderer at init

    return game_map

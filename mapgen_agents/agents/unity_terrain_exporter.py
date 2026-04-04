"""
UnityTerrainExporter — Exports heightmaps, splatmaps, and terrain configuration
for Unity's built-in Terrain system.

Outputs:
  - heightmap.raw (16-bit RAW file Unity can import directly)
  - splatmap_0.png (RGBA texture: R=grass, G=rock, B=sand, A=snow)
  - terrain_config.json (Unity terrain settings: size, resolution, layers)
"""

import numpy as np
import struct
import json
import os
from base_agent import BaseAgent
from shared_state import SharedState
from typing import Any
from PIL import Image


class UnityTerrainExporter(BaseAgent):
    name = "UnityTerrainExporter"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        output_dir = params.get("output_dir",
                                "/sessions/brave-busy-fermat/mnt/outputs/unity_export")
        terrain_dir = os.path.join(output_dir, "Terrain")
        os.makedirs(terrain_dir, exist_ok=True)

        h, w = shared_state.config.height, shared_state.config.width
        biome = shared_state.config.biome

        # ── 1. Export heightmap as 16-bit RAW ──
        heightmap_path = os.path.join(terrain_dir, "heightmap.raw")
        self._export_heightmap_raw(shared_state.elevation, heightmap_path)

        # ── 2. Export heightmap as PNG (for preview / fallback import) ──
        heightmap_png_path = os.path.join(terrain_dir, "heightmap.png")
        self._export_heightmap_png(shared_state.elevation, heightmap_png_path)

        # ── 3. Generate splatmap (terrain texture blending) ──
        splatmap_path = os.path.join(terrain_dir, "splatmap_0.png")
        self._export_splatmap(shared_state, splatmap_path)

        # ── 4. Export water mask ──
        water_path = os.path.join(terrain_dir, "water_mask.png")
        water_img = Image.fromarray((shared_state.water_mask * 255).astype(np.uint8), 'L')
        water_img.save(water_path)

        # ── 5. Export walkability mask ──
        walk_path = os.path.join(terrain_dir, "walkability_mask.png")
        walk_img = Image.fromarray((shared_state.walkability * 255).astype(np.uint8), 'L')
        walk_img.save(walk_path)

        # ── 6. Terrain configuration JSON ──
        config_path = os.path.join(terrain_dir, "terrain_config.json")
        terrain_config = {
            "terrainSize": {
                "x": w,
                "y": 100,  # max terrain height in Unity units
                "z": h,
            },
            "heightmapResolution": max(w, h) + 1,  # Unity requires power of 2 + 1
            "alphamapResolution": max(w, h),
            "baseMapResolution": 1024,
            "detailResolution": 512,
            "detailResolutionPerPatch": 8,
            "heightmapFile": "heightmap.raw",
            "heightmapPNG": "heightmap.png",
            "splatmapFile": "splatmap_0.png",
            "waterMask": "water_mask.png",
            "walkabilityMask": "walkability_mask.png",
            "biome": biome,
            "seed": shared_state.config.seed,
            "terrainLayers": self._get_terrain_layers(biome),
            "importSettings": {
                "rawFormat": "RAW16_LittleEndian",
                "flipVertically": False,
                "resolution": max(w, h),
                "byteOrder": "Windows",
            }
        }

        with open(config_path, 'w') as f:
            json.dump(terrain_config, f, indent=2)

        return {
            "heightmap": heightmap_path,
            "heightmap_png": heightmap_png_path,
            "splatmap": splatmap_path,
            "config": config_path,
            "terrain_size": f"{w}x{h}",
            "output_dir": terrain_dir,
        }

    def _export_heightmap_raw(self, elevation: np.ndarray, path: str):
        """Export heightmap as 16-bit unsigned RAW file (Unity's native format)."""
        # Normalize to 0–65535 range
        normalized = (elevation * 65535).astype(np.uint16)
        # Unity expects little-endian
        with open(path, 'wb') as f:
            f.write(normalized.tobytes())

    def _export_heightmap_png(self, elevation: np.ndarray, path: str):
        """Export heightmap as 16-bit grayscale PNG."""
        normalized = (elevation * 255).astype(np.uint8)
        img = Image.fromarray(normalized, 'L')
        img.save(path)

    def _export_splatmap(self, state: SharedState, path: str):
        """
        Generate a splatmap (RGBA) for Unity terrain texture blending.
        R = base terrain (grass/sand/stone depending on biome)
        G = secondary (rock/gravel)
        B = tertiary (sand/dirt)
        A = special (snow/lava/moss)
        """
        h, w = state.config.height, state.config.width
        splatmap = np.zeros((h, w, 4), dtype=np.uint8)

        elevation = state.elevation
        moisture = state.moisture
        biome = state.config.biome

        for y in range(h):
            for x in range(w):
                e = elevation[y, x]
                m = moisture[y, x]

                if state.water_mask[y, x]:
                    # Water areas: sand/mud underneath
                    splatmap[y, x] = [0, 0, 255, 0]
                elif biome in ("forest", "plains", "swamp"):
                    if e < 0.4:
                        splatmap[y, x] = [255, 0, 0, 0]   # grass
                    elif e < 0.7:
                        blend = int((e - 0.4) / 0.3 * 255)
                        splatmap[y, x] = [255 - blend, blend, 0, 0]  # grass→rock
                    else:
                        splatmap[y, x] = [0, 255, 0, 0]   # rock
                elif biome in ("mountain", "tundra"):
                    if e < 0.3:
                        splatmap[y, x] = [255, 0, 0, 0]   # grass
                    elif e < 0.6:
                        splatmap[y, x] = [0, 255, 0, 0]   # rock
                    elif e < 0.8:
                        blend = int((e - 0.6) / 0.2 * 255)
                        splatmap[y, x] = [0, 255 - blend, 0, blend]  # rock→snow
                    else:
                        splatmap[y, x] = [0, 0, 0, 255]   # snow
                elif biome == "desert":
                    if e < 0.5:
                        splatmap[y, x] = [0, 0, 255, 0]   # sand
                    else:
                        blend = int((e - 0.5) / 0.5 * 255)
                        splatmap[y, x] = [0, blend, 255 - blend, 0]  # sand→rock
                elif biome == "volcanic":
                    if e < 0.3:
                        splatmap[y, x] = [0, 0, 0, 255]   # lava
                    elif e < 0.6:
                        splatmap[y, x] = [0, 0, 255, 0]   # ash
                    else:
                        splatmap[y, x] = [0, 255, 0, 0]   # obsidian rock
                else:
                    # Default: elevation-based blend
                    splatmap[y, x] = [int((1-e)*255), int(e*255), 0, 0]

        img = Image.fromarray(splatmap, 'RGBA')
        img.save(path)

    def _get_terrain_layers(self, biome: str) -> list[dict]:
        """Return Unity TerrainLayer definitions for this biome."""
        layers = {
            "forest": [
                {"name": "Grass", "channel": "R", "texture": "Textures/Terrain/Grass_01"},
                {"name": "Rock", "channel": "G", "texture": "Textures/Terrain/Rock_01"},
                {"name": "Dirt", "channel": "B", "texture": "Textures/Terrain/Dirt_01"},
                {"name": "Moss", "channel": "A", "texture": "Textures/Terrain/Moss_01"},
            ],
            "mountain": [
                {"name": "Grass", "channel": "R", "texture": "Textures/Terrain/Alpine_Grass"},
                {"name": "Rock", "channel": "G", "texture": "Textures/Terrain/Mountain_Rock"},
                {"name": "Gravel", "channel": "B", "texture": "Textures/Terrain/Gravel_01"},
                {"name": "Snow", "channel": "A", "texture": "Textures/Terrain/Snow_01"},
            ],
            "desert": [
                {"name": "Sand_Light", "channel": "R", "texture": "Textures/Terrain/Sand_Light"},
                {"name": "Rock", "channel": "G", "texture": "Textures/Terrain/Desert_Rock"},
                {"name": "Sand_Dark", "channel": "B", "texture": "Textures/Terrain/Sand_Dark"},
                {"name": "Cracked", "channel": "A", "texture": "Textures/Terrain/Cracked_Earth"},
            ],
            "swamp": [
                {"name": "Mud", "channel": "R", "texture": "Textures/Terrain/Mud_01"},
                {"name": "Wet_Grass", "channel": "G", "texture": "Textures/Terrain/Wet_Grass"},
                {"name": "Silt", "channel": "B", "texture": "Textures/Terrain/Silt_01"},
                {"name": "Moss", "channel": "A", "texture": "Textures/Terrain/Swamp_Moss"},
            ],
            "volcanic": [
                {"name": "Ash", "channel": "R", "texture": "Textures/Terrain/Volcanic_Ash"},
                {"name": "Obsidian", "channel": "G", "texture": "Textures/Terrain/Obsidian"},
                {"name": "Charred", "channel": "B", "texture": "Textures/Terrain/Charred_Earth"},
                {"name": "Lava_Crust", "channel": "A", "texture": "Textures/Terrain/Lava_Crust"},
            ],
        }
        return layers.get(biome, layers["forest"])

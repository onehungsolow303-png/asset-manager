"""
UnityTilemapExporter — Exports tilemap data for Unity's 2D Tilemap system.
Generates tile indices, palette definitions, and a Tilemap-compatible JSON format
that can be loaded at runtime or converted into Unity Tilemap assets.

Useful for top-down 2D views or minimap overlays.
"""

import os
import json
import numpy as np
from base_agent import BaseAgent
from shared_state import SharedState
from typing import Any
from PIL import Image


# Tile type definitions per biome
TILE_PALETTES = {
    "forest": {
        0: {"name": "grass", "color": [50, 120, 50], "walkable": True},
        1: {"name": "dark_grass", "color": [34, 85, 34], "walkable": True},
        2: {"name": "dirt_path", "color": [140, 115, 80], "walkable": True},
        3: {"name": "water", "color": [60, 130, 180], "walkable": False},
        4: {"name": "rock", "color": [139, 137, 112], "walkable": False},
        5: {"name": "tree", "color": [25, 80, 25], "walkable": False},
        6: {"name": "building_floor", "color": [120, 90, 60], "walkable": True},
        7: {"name": "building_wall", "color": [100, 70, 40], "walkable": False},
        8: {"name": "door", "color": [60, 40, 25], "walkable": True},
        9: {"name": "bush", "color": [35, 70, 20], "walkable": True},
    },
    "dungeon": {
        0: {"name": "void", "color": [20, 18, 15], "walkable": False},
        1: {"name": "stone_floor", "color": [75, 70, 62], "walkable": True},
        2: {"name": "stone_wall", "color": [45, 40, 35], "walkable": False},
        3: {"name": "corridor", "color": [80, 75, 65], "walkable": True},
        4: {"name": "water", "color": [40, 60, 90], "walkable": False},
        5: {"name": "door", "color": [90, 60, 30], "walkable": True},
        6: {"name": "chest", "color": [150, 120, 40], "walkable": False},
        7: {"name": "torch", "color": [200, 150, 40], "walkable": True},
        8: {"name": "rubble", "color": [60, 55, 48], "walkable": True},
        9: {"name": "pit", "color": [10, 8, 5], "walkable": False},
    },
    "desert": {
        0: {"name": "sand", "color": [210, 190, 140], "walkable": True},
        1: {"name": "dark_sand", "color": [180, 150, 100], "walkable": True},
        2: {"name": "path", "color": [170, 150, 110], "walkable": True},
        3: {"name": "oasis_water", "color": [50, 120, 160], "walkable": False},
        4: {"name": "rock", "color": [160, 140, 110], "walkable": False},
        5: {"name": "cactus", "color": [50, 100, 40], "walkable": False},
        6: {"name": "building", "color": [150, 130, 90], "walkable": False},
        7: {"name": "dune", "color": [200, 180, 140], "walkable": True},
    },
    "mountain": {
        0: {"name": "grass", "color": [80, 120, 60], "walkable": True},
        1: {"name": "rock", "color": [130, 130, 110], "walkable": True},
        2: {"name": "path", "color": [150, 140, 125], "walkable": True},
        3: {"name": "water", "color": [50, 110, 160], "walkable": False},
        4: {"name": "cliff", "color": [170, 165, 155], "walkable": False},
        5: {"name": "snow", "color": [240, 240, 245], "walkable": True},
        6: {"name": "building", "color": [100, 90, 70], "walkable": False},
        7: {"name": "pine_tree", "color": [20, 60, 25], "walkable": False},
    },
    "cave": {
        0: {"name": "void", "color": [30, 28, 25], "walkable": False},
        1: {"name": "cave_floor", "color": [55, 50, 45], "walkable": True},
        2: {"name": "cave_wall", "color": [40, 36, 32], "walkable": False},
        3: {"name": "water_pool", "color": [35, 55, 80], "walkable": False},
        4: {"name": "rock", "color": [80, 75, 65], "walkable": False},
        5: {"name": "crystal", "color": [80, 140, 180], "walkable": False},
        6: {"name": "mushroom", "color": [120, 70, 120], "walkable": True},
    },
    "mine": {
        0: {"name": "rock_wall", "color": [45, 40, 32], "walkable": False},
        1: {"name": "tunnel_floor", "color": [70, 62, 50], "walkable": True},
        2: {"name": "rail", "color": [100, 90, 70], "walkable": True},
        3: {"name": "ore_gold", "color": [140, 120, 40], "walkable": False},
        4: {"name": "ore_silver", "color": [120, 130, 140], "walkable": False},
        5: {"name": "support_beam", "color": [110, 85, 50], "walkable": False},
        6: {"name": "shaft_room", "color": [72, 65, 52], "walkable": True},
    },
    "maze": {
        0: {"name": "wall", "color": [50, 45, 38], "walkable": False},
        1: {"name": "path_floor", "color": [85, 80, 70], "walkable": True},
        2: {"name": "door", "color": [90, 60, 30], "walkable": True},
        3: {"name": "dead_end", "color": [75, 70, 60], "walkable": True},
    },
    "castle": {
        0: {"name": "ground", "color": [80, 120, 60], "walkable": True},
        1: {"name": "stone_wall", "color": [80, 75, 65], "walkable": False},
        2: {"name": "stone_floor", "color": [110, 100, 85], "walkable": True},
        3: {"name": "tower", "color": [70, 65, 55], "walkable": False},
        4: {"name": "gate", "color": [60, 40, 25], "walkable": True},
        5: {"name": "water_moat", "color": [40, 80, 130], "walkable": False},
        6: {"name": "path", "color": [140, 115, 80], "walkable": True},
    },
    "arena": {
        0: {"name": "arena_floor", "color": [150, 135, 105], "walkable": True},
        1: {"name": "wall", "color": [90, 80, 65], "walkable": False},
        2: {"name": "obstacle", "color": [100, 90, 70], "walkable": False},
        3: {"name": "gate", "color": [60, 40, 25], "walkable": True},
    },
    "crash_site": {
        0: {"name": "ground", "color": [80, 110, 50], "walkable": True},
        1: {"name": "scorched", "color": [65, 55, 42], "walkable": True},
        2: {"name": "crater", "color": [55, 48, 40], "walkable": True},
        3: {"name": "debris", "color": [90, 85, 78], "walkable": False},
        4: {"name": "wreckage", "color": [70, 65, 60], "walkable": False},
    },
    "treasure_room": {
        0: {"name": "void", "color": [30, 25, 20], "walkable": False},
        1: {"name": "gold_floor", "color": [100, 85, 50], "walkable": True},
        2: {"name": "wall", "color": [60, 55, 45], "walkable": False},
        3: {"name": "pillar", "color": [80, 70, 55], "walkable": False},
        4: {"name": "treasure", "color": [200, 170, 40], "walkable": False},
    },
    "crypt": {
        0: {"name": "void", "color": [25, 22, 18], "walkable": False},
        1: {"name": "stone_floor", "color": [65, 60, 52], "walkable": True},
        2: {"name": "stone_wall", "color": [40, 38, 32], "walkable": False},
        3: {"name": "sarcophagus", "color": [50, 45, 38], "walkable": False},
        4: {"name": "corridor", "color": [70, 65, 55], "walkable": True},
        5: {"name": "bones", "color": [180, 175, 165], "walkable": True},
    },
    "tomb": {
        0: {"name": "void", "color": [30, 26, 22], "walkable": False},
        1: {"name": "stone_floor", "color": [70, 62, 52], "walkable": True},
        2: {"name": "stone_wall", "color": [45, 40, 35], "walkable": False},
        3: {"name": "gold_accent", "color": [90, 75, 40], "walkable": True},
        4: {"name": "sarcophagus", "color": [55, 48, 40], "walkable": False},
        5: {"name": "corridor", "color": [68, 60, 50], "walkable": True},
    },
    "graveyard": {
        0: {"name": "grass", "color": [50, 100, 45], "walkable": True},
        1: {"name": "dirt_path", "color": [120, 100, 70], "walkable": True},
        2: {"name": "headstone", "color": [160, 155, 145], "walkable": False},
        3: {"name": "fence", "color": [50, 45, 35], "walkable": False},
        4: {"name": "building", "color": [110, 105, 95], "walkable": False},
        5: {"name": "dead_grass", "color": [90, 85, 55], "walkable": True},
    },
    "dock": {
        0: {"name": "ground", "color": [80, 110, 50], "walkable": True},
        1: {"name": "wood_plank", "color": [110, 85, 50], "walkable": True},
        2: {"name": "water", "color": [40, 90, 150], "walkable": False},
        3: {"name": "building", "color": [100, 80, 55], "walkable": False},
        4: {"name": "sand", "color": [194, 178, 128], "walkable": True},
        5: {"name": "rope", "color": [140, 120, 80], "walkable": True},
    },
    "factory": {
        0: {"name": "ground", "color": [80, 100, 55], "walkable": True},
        1: {"name": "metal_floor", "color": [95, 90, 85], "walkable": True},
        2: {"name": "wall", "color": [70, 68, 65], "walkable": False},
        3: {"name": "machinery", "color": [110, 108, 105], "walkable": False},
        4: {"name": "loading_bay", "color": [80, 75, 68], "walkable": True},
    },
    "shop": {
        0: {"name": "ground", "color": [80, 110, 50], "walkable": True},
        1: {"name": "wood_floor", "color": [125, 100, 70], "walkable": True},
        2: {"name": "wall", "color": [105, 82, 55], "walkable": False},
        3: {"name": "counter", "color": [120, 95, 65], "walkable": False},
        4: {"name": "door", "color": [80, 55, 30], "walkable": True},
    },
    "shopping_center": {
        0: {"name": "cobblestone", "color": [130, 120, 100], "walkable": True},
        1: {"name": "shop_floor", "color": [125, 100, 70], "walkable": True},
        2: {"name": "wall", "color": [105, 82, 55], "walkable": False},
        3: {"name": "stall", "color": [115, 90, 60], "walkable": False},
        4: {"name": "path", "color": [140, 115, 80], "walkable": True},
    },
    "temple": {
        0: {"name": "ground", "color": [80, 110, 50], "walkable": True},
        1: {"name": "marble_floor", "color": [160, 155, 145], "walkable": True},
        2: {"name": "stone_wall", "color": [120, 115, 105], "walkable": False},
        3: {"name": "pillar", "color": [130, 125, 115], "walkable": False},
        4: {"name": "altar", "color": [180, 170, 140], "walkable": False},
        5: {"name": "sanctum_floor", "color": [170, 165, 150], "walkable": True},
    },
    "church": {
        0: {"name": "ground", "color": [80, 110, 50], "walkable": True},
        1: {"name": "stone_floor", "color": [150, 145, 135], "walkable": True},
        2: {"name": "stone_wall", "color": [110, 105, 95], "walkable": False},
        3: {"name": "altar", "color": [170, 160, 140], "walkable": False},
        4: {"name": "pew", "color": [100, 75, 45], "walkable": False},
        5: {"name": "door", "color": [80, 55, 30], "walkable": True},
    },
    "biomes": {
        0: {"name": "grass", "color": [50, 120, 50], "walkable": True},
        1: {"name": "sand", "color": [210, 190, 140], "walkable": True},
        2: {"name": "snow", "color": [240, 240, 245], "walkable": True},
        3: {"name": "rock", "color": [130, 130, 110], "walkable": True},
        4: {"name": "water", "color": [60, 130, 180], "walkable": False},
        5: {"name": "tree", "color": [25, 80, 25], "walkable": False},
        6: {"name": "building", "color": [120, 90, 60], "walkable": False},
        7: {"name": "path", "color": [140, 115, 80], "walkable": True},
    },
}


class UnityTilemapExporter(BaseAgent):
    name = "UnityTilemapExporter"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        output_dir = params.get("output_dir",
                                "./output/unity_export")
        tilemap_dir = os.path.join(output_dir, "Tilemap")
        os.makedirs(tilemap_dir, exist_ok=True)

        h, w = shared_state.config.height, shared_state.config.width
        biome = shared_state.config.biome
        tile_size = params.get("tile_size", 4)  # pixels per tile

        # Get palette for this biome
        palette = TILE_PALETTES.get(biome, TILE_PALETTES["forest"])

        # ── 1. Generate tile index grid ──
        tile_grid = self._classify_tiles(shared_state, palette, tile_size)
        tile_h, tile_w = tile_grid.shape

        # ── 2. Export tilemap data JSON ──
        tilemap_data_path = os.path.join(tilemap_dir, "tilemap_data.json")
        self._export_tilemap_json(tile_grid, palette, tile_size, shared_state, tilemap_data_path)

        # ── 3. Generate tile palette image (sprite sheet) ──
        palette_path = os.path.join(tilemap_dir, "tile_palette.png")
        self._generate_palette_image(palette, palette_path)

        # ── 4. Generate tilemap preview image ──
        preview_path = os.path.join(tilemap_dir, "tilemap_preview.png")
        self._generate_tilemap_preview(tile_grid, palette, preview_path, tile_size=4)

        # ── 5. Generate collision map ──
        collision_path = os.path.join(tilemap_dir, "collision_map.json")
        self._export_collision_map(tile_grid, palette, collision_path)

        # ── 6. Generate C# TilemapLoader script ──
        loader_path = os.path.join(tilemap_dir, "TilemapLoader.cs")
        self._write_tilemap_loader(loader_path)

        return {
            "tilemap_size": f"{tile_w}x{tile_h}",
            "tile_size": tile_size,
            "tile_types": len(palette),
            "data_file": tilemap_data_path,
            "palette_image": palette_path,
            "preview_image": preview_path,
            "output_dir": tilemap_dir,
        }

    def _classify_tiles(self, state: SharedState, palette: dict,
                         tile_size: int) -> np.ndarray:
        """Classify each tile cell based on map state."""
        h, w = state.config.height, state.config.width
        tile_h = h // tile_size
        tile_w = w // tile_size

        grid = np.zeros((tile_h, tile_w), dtype=np.uint8)

        for ty in range(tile_h):
            for tx in range(tile_w):
                # Sample the center of the tile
                py = ty * tile_size + tile_size // 2
                px = tx * tile_size + tile_size // 2
                py = min(py, h - 1)
                px = min(px, w - 1)

                # Priority-based classification
                if state.water_mask[py, px]:
                    # Find "water" tile in palette
                    grid[ty, tx] = self._find_tile_by_name(palette, "water", 3)
                elif state.structure_mask[py, px]:
                    # Check if wall or floor
                    if not state.walkability[py, px]:
                        grid[ty, tx] = self._find_tile_by_name(palette, "wall", 7)
                    else:
                        grid[ty, tx] = self._find_tile_by_name(palette, "floor", 6)
                elif any(p.path_type == "road" for p in state.paths):
                    # Check if on a road
                    on_road = False
                    for path in state.paths:
                        if path.path_type == "road":
                            for wp_x, wp_y in path.waypoints:
                                if abs(wp_x - px) < tile_size and abs(wp_y - py) < tile_size:
                                    on_road = True
                                    break
                        if on_road:
                            break
                    if on_road:
                        grid[ty, tx] = self._find_tile_by_name(palette, "path", 2)
                    else:
                        # Base terrain
                        elev = state.elevation[py, px]
                        if elev > 0.75:
                            grid[ty, tx] = self._find_tile_by_name(palette, "rock", 4)
                        elif elev < 0.3:
                            grid[ty, tx] = 0  # base terrain
                        else:
                            grid[ty, tx] = 1  # secondary terrain
                else:
                    elev = state.elevation[py, px]
                    if elev > 0.75:
                        grid[ty, tx] = self._find_tile_by_name(palette, "rock", 4)
                    else:
                        grid[ty, tx] = 0

        return grid

    def _find_tile_by_name(self, palette: dict, name_fragment: str, default: int) -> int:
        """Find a tile index by partial name match."""
        for idx, tile in palette.items():
            if name_fragment in tile["name"]:
                return idx
        return default

    def _export_tilemap_json(self, grid: np.ndarray, palette: dict,
                              tile_size: int, state: SharedState, path: str):
        """Export tilemap as Unity-compatible JSON."""
        tile_h, tile_w = grid.shape

        data = {
            "format": "unity_tilemap",
            "version": "1.0",
            "gridSize": {"x": tile_w, "y": tile_h},
            "tileSize": tile_size,
            "mapConfig": {
                "biome": state.config.biome,
                "mapType": state.config.map_type,
                "seed": state.config.seed,
            },
            "palette": {str(k): v for k, v in palette.items()},
            "layers": {
                "ground": grid.tolist(),
            },
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f)  # compact for large grids

    def _generate_palette_image(self, palette: dict, path: str):
        """Generate a tile palette sprite sheet (one tile per row)."""
        tile_px = 32  # pixels per tile in sprite sheet
        num_tiles = len(palette)

        img = Image.new('RGBA', (tile_px, tile_px * num_tiles), (0, 0, 0, 0))

        for idx, tile_info in palette.items():
            color = tuple(tile_info["color"]) + (255,)
            tile_img = Image.new('RGBA', (tile_px, tile_px), color)
            img.paste(tile_img, (0, idx * tile_px))

        img.save(path)

    def _generate_tilemap_preview(self, grid: np.ndarray, palette: dict,
                                    path: str, tile_size: int = 4):
        """Generate a preview image of the tilemap."""
        tile_h, tile_w = grid.shape
        img = Image.new('RGB', (tile_w * tile_size, tile_h * tile_size))

        for ty in range(tile_h):
            for tx in range(tile_w):
                tile_idx = grid[ty, tx]
                color = tuple(palette.get(int(tile_idx), palette[0])["color"])
                for dy in range(tile_size):
                    for dx in range(tile_size):
                        img.putpixel((tx * tile_size + dx, ty * tile_size + dy), color)

        img.save(path)

    def _export_collision_map(self, grid: np.ndarray, palette: dict, path: str):
        """Export walkability data for Unity's collision/navmesh system."""
        tile_h, tile_w = grid.shape
        collision = np.ones((tile_h, tile_w), dtype=bool)

        for ty in range(tile_h):
            for tx in range(tile_w):
                tile_idx = int(grid[ty, tx])
                tile_info = palette.get(tile_idx, palette[0])
                collision[ty, tx] = tile_info["walkable"]

        data = {
            "gridSize": {"x": tile_w, "y": tile_h},
            "walkable": collision.tolist(),
            "walkablePercent": float(collision.mean() * 100),
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

    def _write_tilemap_loader(self, path: str):
        code = '''using UnityEngine;
using UnityEngine.Tilemaps;
using System.IO;
using System.Collections.Generic;

/// <summary>
/// Loads procedurally generated tilemap data into Unity's Tilemap system.
/// Reads tilemap_data.json and spawns tiles at runtime.
/// </summary>
public class TilemapLoader : MonoBehaviour
{
    [Header("Data")]
    [Tooltip("Path relative to StreamingAssets")]
    public string tilemapDataPath = "Tilemap/tilemap_data.json";

    [Header("References")]
    public Tilemap groundTilemap;
    public Tilemap collisionTilemap;

    [Header("Tile Assets")]
    [Tooltip("Assign tiles in order matching the palette indices")]
    public TileBase[] tilePalette;

    [Header("Collision")]
    public TileBase collisionTile;

    public void LoadTilemap()
    {
        string fullPath = Path.Combine(Application.streamingAssetsPath, tilemapDataPath);

        if (!File.Exists(fullPath))
        {
            Debug.LogError($"TilemapLoader: Data not found at {fullPath}");
            return;
        }

        string json = File.ReadAllText(fullPath);
        TilemapData data = JsonUtility.FromJson<TilemapData>(json);

        if (data == null || data.layers == null)
        {
            Debug.LogError("TilemapLoader: Failed to parse tilemap data");
            return;
        }

        int width = data.gridSize.x;
        int height = data.gridSize.y;

        // Place ground tiles
        if (groundTilemap != null && data.layers.ground != null)
        {
            for (int y = 0; y < height; y++)
            {
                for (int x = 0; x < width; x++)
                {
                    int tileIdx = data.layers.ground[y * width + x];
                    if (tileIdx >= 0 && tileIdx < tilePalette.Length)
                    {
                        Vector3Int pos = new Vector3Int(x, height - 1 - y, 0);
                        groundTilemap.SetTile(pos, tilePalette[tileIdx]);
                    }
                }
            }
        }

        Debug.Log($"TilemapLoader: Loaded {width}x{height} tilemap");
    }

    void Start()
    {
        LoadTilemap();
    }
}

[System.Serializable]
public class TilemapData
{
    public string format;
    public string version;
    public GridSize gridSize;
    public int tileSize;
    public TilemapLayers layers;
}

[System.Serializable]
public class GridSize
{
    public int x;
    public int y;
}

[System.Serializable]
public class TilemapLayers
{
    public int[] ground;
}
'''
        with open(path, 'w', encoding='utf-8') as f:
            f.write(code)

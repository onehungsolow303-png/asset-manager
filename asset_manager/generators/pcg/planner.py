"""
Strategic Planner (Top-Tier) — Decomposes high-level goals into TaskDAGs.
Can use Claude API for creative goal decomposition, or fall back to templates.
All DAGs now include Unity export steps as final pipeline stages.
"""

import json
from .dag_engine import TaskDAG, TaskNode
from .llm_adapter import create_adapter, LLMAdapter, MockLLMAdapter
from .llm_adapter import PLANNER_SYSTEM_PROMPT, build_planner_prompt
from typing import Any, Optional


# Unity export nodes appended to every DAG template
def _unity_export_nodes(render_deps: list[str]) -> list[TaskNode]:
    """Standard Unity export nodes that run after the render step."""
    return [
        TaskNode("unity_terrain", "UnityTerrainExporter", {},
                 ["terrain_base"]),
        TaskNode("unity_scene", "UnitySceneExporter", {},
                 render_deps),
        TaskNode("unity_csharp", "UnityCSharpExporter", {},
                 render_deps),
        TaskNode("unity_tilemap", "UnityTilemapExporter", {},
                 ["terrain_base"]),
    ]


# DAG templates for each map type (now with Unity export steps)
DAG_TEMPLATES = {
    # ── Settlements ──
    "village": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("water_system", "WaterAgent", {"type": "river", "count": 1}, ["terrain_base"]),
        TaskNode("road_network", "PathfindingAgent", {"road_density": "medium"}, ["terrain_base", "water_system"]),
        TaskNode("buildings", "StructureAgent", {"type": "village", "building_count": 10}, ["road_network"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["buildings"]),
        TaskNode("vegetation", "AssetAgent", {"density": "high"}, ["terrain_base", "buildings"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["buildings", "water_system"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "spawns"]),
    ],
    "town": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("water_system", "WaterAgent", {"type": "river", "count": 1}, ["terrain_base"]),
        TaskNode("road_network", "PathfindingAgent", {"road_density": "high"}, ["terrain_base", "water_system"]),
        TaskNode("buildings", "StructureAgent", {"type": "town", "building_count": 15}, ["road_network"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["buildings"]),
        TaskNode("vegetation", "AssetAgent", {"density": "medium"}, ["terrain_base", "buildings"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["buildings", "water_system"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "spawns"]),
    ],
    "city": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("water_system", "WaterAgent", {"type": "river", "count": 1, "lake_count": 1}, ["terrain_base"]),
        TaskNode("road_network", "PathfindingAgent", {"road_density": "high", "road_type": "road"}, ["terrain_base", "water_system"]),
        TaskNode("buildings", "StructureAgent", {"type": "city", "building_count": 20}, ["road_network"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["buildings"]),
        TaskNode("vegetation", "AssetAgent", {"density": "low"}, ["terrain_base", "buildings"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy", "lore_depth": "high"}, ["buildings", "water_system"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "spawns"]),
    ],

    # ── Fortifications ──
    "castle": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("water_system", "WaterAgent", {"type": "lake", "lake_count": 1}, ["terrain_base"]),
        TaskNode("structure", "StructureAgent", {"type": "castle", "building_count": 6}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["structure"]),
        TaskNode("road_network", "PathfindingAgent", {"road_density": "low"}, ["terrain_base", "structure"]),
        TaskNode("vegetation", "AssetAgent", {"density": "low"}, ["terrain_base", "structure"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy", "lore_depth": "high"}, ["structure", "water_system"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "road_network", "spawns"]),
    ],
    "fort": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("structure", "StructureAgent", {"type": "fort", "building_count": 5}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["structure"]),
        TaskNode("road_network", "PathfindingAgent", {"road_density": "low"}, ["terrain_base", "structure"]),
        TaskNode("vegetation", "AssetAgent", {"density": "medium"}, ["terrain_base", "structure"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["structure"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "road_network", "spawns"]),
    ],
    "tower": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("structure", "StructureAgent", {"type": "tower", "building_count": 3}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["structure"]),
        TaskNode("vegetation", "AssetAgent", {"density": "medium"}, ["terrain_base", "structure"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["structure"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "spawns"]),
    ],

    # ── Underground / Interior ──
    "dungeon": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "dungeon"}),
        TaskNode("rooms", "StructureAgent", {"type": "dungeon", "building_count": 8}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["rooms"]),
        TaskNode("props", "AssetAgent", {"theme": "dungeon", "density": "medium"}, ["rooms"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["rooms"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True, "show_grid": True}, ["props", "labeling", "spawns"]),
    ],
    "cave": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "cave"}),
        TaskNode("water_system", "WaterAgent", {"type": "lake", "lake_count": 2}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["water_system"]),
        TaskNode("props", "AssetAgent", {"theme": "cave", "density": "medium"}, ["terrain_base", "water_system"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["water_system"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["props", "labeling", "spawns"]),
    ],
    "mine": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "cave"}),
        TaskNode("tunnels", "StructureAgent", {"type": "mine", "building_count": 5, "branch_count": 6}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["tunnels"]),
        TaskNode("props", "AssetAgent", {"theme": "cave", "density": "low"}, ["tunnels"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["tunnels"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["props", "labeling", "spawns"]),
    ],
    "maze": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "dungeon"}),
        TaskNode("maze_gen", "StructureAgent", {"type": "maze"}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["maze_gen"]),
        TaskNode("props", "AssetAgent", {"theme": "dungeon", "density": "low"}, ["maze_gen"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["maze_gen"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True, "show_grid": True}, ["props", "labeling", "spawns"]),
    ],
    "treasure_room": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "dungeon"}),
        TaskNode("vault", "StructureAgent", {"type": "treasure_room", "building_count": 5}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["vault"]),
        TaskNode("props", "AssetAgent", {"theme": "dungeon", "density": "high"}, ["vault"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy", "lore_depth": "high"}, ["vault"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["props", "labeling", "spawns"]),
    ],

    # ── Combat / Encounter ──
    "arena": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("arena_gen", "StructureAgent", {"type": "arena", "building_count": 6}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["arena_gen"]),
        TaskNode("props", "AssetAgent", {"density": "low"}, ["arena_gen"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["arena_gen"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_grid": True, "show_labels": True}, ["props", "labeling", "spawns"]),
    ],

    # ── Field / Outdoor ──
    "wilderness": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("water_system", "WaterAgent", {"type": "both", "count": 1, "lake_count": 1}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["water_system"]),
        TaskNode("vegetation", "AssetAgent", {"density": "high"}, ["terrain_base", "water_system"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["water_system"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "spawns"]),
    ],
    "camp": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("path", "PathfindingAgent", {"road_density": "low"}, ["terrain_base"]),
        TaskNode("tents", "StructureAgent", {"type": "camp", "building_count": 5}, ["path"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["tents"]),
        TaskNode("props", "AssetAgent", {"density": "medium"}, ["terrain_base", "tents"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["tents"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["props", "labeling", "spawns"]),
    ],
    "outpost": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("road_network", "PathfindingAgent", {"road_density": "low"}, ["terrain_base"]),
        TaskNode("structures", "StructureAgent", {"type": "outpost", "building_count": 4}, ["road_network"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["structures"]),
        TaskNode("vegetation", "AssetAgent", {"density": "medium"}, ["terrain_base", "structures"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["structures"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "spawns"]),
    ],
    "rest_area": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("structures", "StructureAgent", {"type": "rest_area", "building_count": 4}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["structures"]),
        TaskNode("vegetation", "AssetAgent", {"density": "high"}, ["terrain_base", "structures"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["structures"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "spawns"]),
    ],
    "crash_site": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("impact", "StructureAgent", {"type": "crash_site", "building_count": 5}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["impact"]),
        TaskNode("props", "AssetAgent", {"density": "medium"}, ["terrain_base", "impact"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["impact"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["props", "labeling", "spawns"]),
    ],

    # ── Religious / Burial ──
    "crypt": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "dungeon"}),
        TaskNode("rooms", "StructureAgent", {"type": "crypt", "building_count": 6}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["rooms"]),
        TaskNode("props", "AssetAgent", {"theme": "dungeon", "density": "medium"}, ["rooms"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["rooms"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["props", "labeling", "spawns"]),
    ],
    "tomb": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "dungeon"}),
        TaskNode("rooms", "StructureAgent", {"type": "tomb", "building_count": 5}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["rooms"]),
        TaskNode("props", "AssetAgent", {"theme": "dungeon", "density": "medium"}, ["rooms"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy", "lore_depth": "high"}, ["rooms"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["props", "labeling", "spawns"]),
    ],
    "graveyard": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("structures", "StructureAgent", {"type": "graveyard", "building_count": 5}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["structures"]),
        TaskNode("vegetation", "AssetAgent", {"density": "medium"}, ["terrain_base", "structures"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["structures"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "spawns"]),
    ],
    "temple": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("structure", "StructureAgent", {"type": "temple", "building_count": 5}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["structure"]),
        TaskNode("road_network", "PathfindingAgent", {"road_density": "low"}, ["terrain_base", "structure"]),
        TaskNode("vegetation", "AssetAgent", {"density": "medium"}, ["terrain_base", "structure"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy", "lore_depth": "high"}, ["structure"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "road_network", "spawns"]),
    ],
    "church": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("structure", "StructureAgent", {"type": "church", "building_count": 4}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["structure"]),
        TaskNode("vegetation", "AssetAgent", {"density": "high"}, ["terrain_base", "structure"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["structure"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "spawns"]),
    ],

    # ── Commercial / Industrial ──
    "shop": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("road_network", "PathfindingAgent", {"road_density": "medium"}, ["terrain_base"]),
        TaskNode("buildings", "StructureAgent", {"type": "shop", "building_count": 4}, ["road_network"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["buildings"]),
        TaskNode("vegetation", "AssetAgent", {"density": "medium"}, ["terrain_base", "buildings"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["buildings"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "spawns"]),
    ],
    "shopping_center": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("road_network", "PathfindingAgent", {"road_density": "high"}, ["terrain_base"]),
        TaskNode("buildings", "StructureAgent", {"type": "shopping_center", "building_count": 8}, ["road_network"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["buildings"]),
        TaskNode("vegetation", "AssetAgent", {"density": "low"}, ["terrain_base", "buildings"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["buildings"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "spawns"]),
    ],
    "factory": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("structure", "StructureAgent", {"type": "factory", "building_count": 5}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["structure"]),
        TaskNode("road_network", "PathfindingAgent", {"road_density": "medium"}, ["terrain_base", "structure"]),
        TaskNode("vegetation", "AssetAgent", {"density": "low"}, ["terrain_base", "structure"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["structure"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "road_network", "spawns"]),
    ],

    # ── Waterfront ──
    "dock": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("water_system", "WaterAgent", {"type": "ocean", "ocean_edge": "south", "ocean_depth_pct": 0.4}, ["terrain_base"]),
        TaskNode("structure", "StructureAgent", {"type": "dock", "building_count": 5}, ["terrain_base", "water_system"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["structure"]),
        TaskNode("road_network", "PathfindingAgent", {"road_density": "medium"}, ["terrain_base", "structure"]),
        TaskNode("vegetation", "AssetAgent", {"density": "low"}, ["terrain_base", "structure"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["structure", "water_system"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "road_network", "spawns"]),
    ],

    # ── Interior / Social ──
    "tavern": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "dungeon"}),
        TaskNode("rooms", "StructureAgent", {"type": "tavern", "building_count": 6}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["rooms"]),
        TaskNode("props", "AssetAgent", {"theme": "tavern", "density": "high"}, ["rooms"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["rooms"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["props", "labeling", "spawns"]),
    ],
    "prison": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "dungeon"}),
        TaskNode("rooms", "StructureAgent", {"type": "prison", "building_count": 8}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["rooms"]),
        TaskNode("road_network", "PathfindingAgent", {"road_density": "low"}, ["terrain_base", "rooms"]),
        TaskNode("props", "AssetAgent", {"theme": "prison", "density": "medium"}, ["rooms"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["rooms"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["props", "labeling", "road_network", "spawns"]),
    ],
    "library": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "dungeon"}),
        TaskNode("rooms", "StructureAgent", {"type": "library", "building_count": 6}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["rooms"]),
        TaskNode("props", "AssetAgent", {"theme": "library", "density": "high"}, ["rooms"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["rooms"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["props", "labeling", "spawns"]),
    ],
    "throne_room": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "dungeon"}),
        TaskNode("rooms", "StructureAgent", {"type": "throne_room", "building_count": 5}, ["terrain_base"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["rooms"]),
        TaskNode("props", "AssetAgent", {"theme": "throne_room", "density": "medium"}, ["rooms"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy", "lore_depth": "high"}, ["rooms"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["props", "labeling", "spawns"]),
    ],

    # ── Waterfront ── (extended)
    "harbor": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("water_system", "WaterAgent", {"type": "ocean", "ocean_edge": "south", "ocean_depth_pct": 0.45}, ["terrain_base"]),
        TaskNode("road_network", "PathfindingAgent", {"road_density": "medium"}, ["terrain_base", "water_system"]),
        TaskNode("structures", "StructureAgent", {"type": "dock", "building_count": 8}, ["road_network", "water_system"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["structures"]),
        TaskNode("vegetation", "AssetAgent", {"density": "low"}, ["terrain_base", "structures"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy"}, ["structures", "water_system"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "spawns"]),
    ],

    # ── Large Scale ──
    "region": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("water_system", "WaterAgent", {"type": "both", "count": 3, "lake_count": 2}, ["terrain_base"]),
        TaskNode("road_network", "PathfindingAgent", {"road_density": "high"}, ["terrain_base", "water_system"]),
        TaskNode("settlements", "StructureAgent", {"type": "village", "building_count": 20}, ["road_network"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["settlements"]),
        TaskNode("vegetation", "AssetAgent", {"density": "high"}, ["terrain_base", "settlements"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy", "lore_depth": "high"}, ["settlements", "water_system"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "spawns"]),
    ],
    "open_world": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("water_system", "WaterAgent", {"type": "both", "count": 2, "lake_count": 2}, ["terrain_base"]),
        TaskNode("road_network", "PathfindingAgent", {"road_density": "high"}, ["terrain_base", "water_system"]),
        TaskNode("settlements", "StructureAgent", {"type": "village", "building_count": 15}, ["road_network"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["settlements"]),
        TaskNode("vegetation", "AssetAgent", {"density": "high"}, ["terrain_base", "settlements"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy", "lore_depth": "high"}, ["settlements", "water_system"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "spawns"]),
    ],
    "biomes": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "forest"}),
        TaskNode("water_system", "WaterAgent", {"type": "both", "count": 2, "lake_count": 2, "stream_count": 3, "pond_count": 2}, ["terrain_base"]),
        TaskNode("road_network", "PathfindingAgent", {"road_density": "medium"}, ["terrain_base", "water_system"]),
        TaskNode("settlements", "StructureAgent", {"type": "village", "building_count": 10}, ["road_network"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["settlements"]),
        TaskNode("vegetation", "AssetAgent", {"density": "high"}, ["terrain_base", "settlements"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy", "lore_depth": "high"}, ["settlements", "water_system"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "spawns"]),
    ],
    "world_box": [
        TaskNode("terrain_base", "TerrainAgent", {"biome": "{biome}"}),
        TaskNode("water_system", "WaterAgent", {"type": "ocean", "ocean_edge": "south", "ocean_depth_pct": 0.2, "count": 3, "lake_count": 2}, ["terrain_base"]),
        TaskNode("road_network", "PathfindingAgent", {"road_density": "high", "road_type": "road"}, ["terrain_base", "water_system"]),
        TaskNode("settlements", "StructureAgent", {"type": "village", "building_count": 25}, ["road_network"]),
        TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["settlements"]),
        TaskNode("vegetation", "AssetAgent", {"density": "high"}, ["terrain_base", "settlements"]),
        TaskNode("labeling", "LabelingAgent", {"style": "fantasy", "lore_depth": "high"}, ["settlements", "water_system"]),
        TaskNode("render", "RendererAgent", {"format": "png", "show_labels": True}, ["vegetation", "labeling", "spawns"]),
    ],
}

# Map size presets
SIZE_PRESETS = {
    "small_encounter": (256, 256),
    "medium_encounter": (512, 512),
    "large_encounter": (768, 768),
    "standard": (512, 512),
    "large": (1024, 1024),
    "region": (1024, 1024),
    "open_world": (1536, 1536),
}


class StrategicPlanner:
    """
    Top-tier planner that decomposes goals into TaskDAGs.
    When a Claude API key is available, uses Claude for creative planning
    and richer labeling. Falls back to template-based planning otherwise.
    """

    def __init__(self, llm: Optional[LLMAdapter] = None):
        self.llm = llm or create_adapter()
        self._use_llm = not isinstance(self.llm, MockLLMAdapter)

    def plan(self, goal: str, map_type: str = "village",
             biome: str = "forest", size: str = "standard",
             seed: int = 42, unity_export: bool = True,
             **kwargs) -> tuple["TaskDAG", dict]:
        """
        Decompose a goal into a TaskDAG.

        Args:
            goal: Natural language description of desired map
            map_type: One of the supported map types
            biome: Terrain biome
            size: Size preset name or (width, height) tuple
            seed: Random seed
            unity_export: If True, append Unity export nodes to the DAG

        Returns:
            (TaskDAG, config_dict)
        """
        # Resolve size
        if isinstance(size, str):
            width, height = SIZE_PRESETS.get(size, SIZE_PRESETS["standard"])
        else:
            width, height = size

        # ── Try LLM-based planning if Claude API is available ──
        if self._use_llm:
            try:
                dag, config = self._plan_with_llm(
                    goal, map_type, biome, (width, height), seed, unity_export, **kwargs)
                if dag is not None:
                    return dag, config
            except Exception as e:
                print(f"[PLANNER] LLM planning failed ({e}), falling back to templates")

        # ── Template-based planning (fallback) ──
        return self._plan_with_templates(
            goal, map_type, biome, width, height, seed, unity_export, **kwargs)

    def _plan_with_llm(self, goal, map_type, biome, size, seed,
                        unity_export, **kwargs) -> tuple:
        """Use Claude API to generate a custom DAG from the goal description."""
        prompt = build_planner_prompt(goal, map_type, biome, size, seed)

        print(f"[PLANNER] Sending goal to Claude for DAG decomposition...")
        result = self.llm.generate_json(prompt, system=PLANNER_SYSTEM_PROMPT)

        if "tasks" not in result:
            return None, None

        # Parse LLM response into TaskDAG
        dag = TaskDAG()
        for task in result["tasks"]:
            dag.add_task(TaskNode(
                task_id=task["task_id"],
                agent_type=task["agent_type"],
                params=task.get("params", {}),
                depends_on=task.get("depends_on", []),
            ))

        # Validate the LLM-generated DAG
        valid, error = dag.validate()
        if not valid:
            print(f"[PLANNER] LLM-generated DAG invalid: {error}")
            return None, None

        config = {
            "width": size[0],
            "height": size[1],
            "biome": biome,
            "map_type": map_type,
            "seed": seed,
            "goal": goal,
            "planned_by": "claude",
            "map_name": result.get("map_name", ""),
        }

        print(f"[PLANNER] Claude generated DAG with {len(dag.nodes)} tasks")
        if result.get("map_name"):
            print(f"[PLANNER] Map name: {result['map_name']}")

        return dag, config

    def _plan_with_templates(self, goal, map_type, biome, width, height,
                              seed, unity_export, **kwargs) -> tuple:
        """Template-based planning (always works, no API needed)."""
        template_key = map_type.lower().replace(" ", "_")
        if template_key not in DAG_TEMPLATES:
            template_key = "village"

        dag = TaskDAG()
        template = DAG_TEMPLATES[template_key]
        output_dir = kwargs.get("output_dir",
                                "./output/unity_export")

        # Track what the render node depends on (for Unity exporters)
        render_deps = []

        for node_template in template:
            params = {}
            for k, v in node_template.params.items():
                if isinstance(v, str) and ("{biome}" in v or "{map_type}" in v):
                    params[k] = v.replace("{biome}", biome).replace("{map_type}", map_type)
                else:
                    params[k] = v

            if node_template.task_id in kwargs:
                params.update(kwargs[node_template.task_id])

            if node_template.agent_type == "RendererAgent":
                params["output_path"] = kwargs.get(
                    "output_path",
                    f"./output/{map_type}_{biome}_{seed}.png"
                )
                render_deps = list(node_template.depends_on)

            dag.add_task(TaskNode(
                task_id=node_template.task_id,
                agent_type=node_template.agent_type,
                params=params,
                depends_on=list(node_template.depends_on),
            ))

        # ── Append Unity export nodes ──
        if unity_export:
            # All Unity exporters need the render to be complete (full shared state)
            all_task_ids = [n.task_id for n in template]
            render_id = "render" if "render" in [n.task_id for n in template] else all_task_ids[-1]

            dag.add_task(TaskNode(
                "unity_terrain", "UnityTerrainExporter",
                {"output_dir": output_dir},
                ["terrain_base"],  # only needs elevation data
            ))
            dag.add_task(TaskNode(
                "unity_tilemap", "UnityTilemapExporter",
                {"output_dir": output_dir},
                [render_id],  # needs complete state
            ))
            dag.add_task(TaskNode(
                "unity_scene", "UnitySceneExporter",
                {"output_dir": output_dir},
                [render_id],
            ))
            dag.add_task(TaskNode(
                "unity_csharp", "UnityCSharpExporter",
                {"output_dir": output_dir},
                [render_id],
            ))

        config = {
            "width": width,
            "height": height,
            "biome": biome,
            "map_type": map_type,
            "seed": seed,
            "goal": goal,
            "planned_by": "template",
            "unity_export": unity_export,
        }

        return dag, config

    def list_map_types(self) -> list[str]:
        return list(DAG_TEMPLATES.keys())

    def list_biomes(self) -> list[str]:
        return ["forest", "mountain", "desert", "swamp", "plains",
                "tundra", "volcanic", "cave", "dungeon",
                "jungle", "underwater", "sky"]

    def list_sizes(self) -> dict:
        return SIZE_PRESETS

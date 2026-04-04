"""
Shared State — The central data layer that all agents read from and write to.
Maintains the map's current state as numpy arrays (grid layers) and lists (entities, paths, labels).
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Any
import json
import time


@dataclass
class Entity:
    """A placed object on the map (building, tree, rock, etc.)"""
    entity_type: str          # "building", "tree", "rock", "chest", etc.
    position: tuple[int, int] # (x, y)
    size: tuple[int, int] = (1, 1)  # (w, h) in grid cells
    variant: str = ""         # visual variant e.g. "oak_large", "stone_wall"
    metadata: dict = field(default_factory=dict)  # name, description, etc.


@dataclass
class PathSegment:
    """A connected path (road, river, corridor)"""
    path_type: str               # "road", "river", "corridor", "trail"
    waypoints: list[tuple[int, int]] = field(default_factory=list)
    width: int = 2
    metadata: dict = field(default_factory=dict)


@dataclass
class Label:
    """A text label placed on the map"""
    text: str
    position: tuple[int, int]
    category: str = "generic"    # "water_feature", "settlement", "landmark", etc.
    font_size: int = 12
    color: str = "#2c1810"


@dataclass
class MapConfig:
    """Configuration for the map being generated"""
    width: int = 512
    height: int = 512
    biome: str = "forest"
    theme: str = "fantasy"
    map_type: str = "village"
    seed: int = 42
    scale: float = 1.0


class SharedState:
    """
    Central shared state that all agents reference.
    Grid layers are numpy arrays, entities/paths/labels are lists.
    Includes locking hints for the orchestrator to manage concurrent access.
    """

    def __init__(self, config: MapConfig):
        self.config = config
        self.rng = np.random.default_rng(config.seed)

        # Grid layers (all float32, 0.0–1.0 unless noted)
        w, h = config.width, config.height
        self.elevation = np.zeros((h, w), dtype=np.float32)
        self.moisture = np.zeros((h, w), dtype=np.float32)
        self.walkability = np.ones((h, w), dtype=bool)       # True = walkable
        self.water_mask = np.zeros((h, w), dtype=bool)        # True = water
        self.structure_mask = np.zeros((h, w), dtype=bool)    # True = structure
        self.terrain_color = np.zeros((h, w, 3), dtype=np.uint8)  # RGB color layer

        # Entity lists
        self.entities: list[Entity] = []
        self.paths: list[PathSegment] = []
        self.labels: list[Label] = []

        # Generation metadata
        self.metadata: dict[str, Any] = {
            "generation_seed": config.seed,
            "map_type": config.map_type,
            "created_at": time.time(),
            "agents_completed": [],
        }

    def log_agent_completion(self, agent_name: str):
        self.metadata["agents_completed"].append({
            "agent": agent_name,
            "timestamp": time.time(),
        })

    def get_walkable_positions(self) -> np.ndarray:
        """Return a boolean mask of all positions that are walkable and not water/structures."""
        return self.walkability & ~self.water_mask & ~self.structure_mask

    def summary(self) -> dict:
        return {
            "map_size": f"{self.config.width}x{self.config.height}",
            "biome": self.config.biome,
            "map_type": self.config.map_type,
            "entities": len(self.entities),
            "paths": len(self.paths),
            "labels": len(self.labels),
            "agents_completed": [a["agent"] for a in self.metadata["agents_completed"]],
        }

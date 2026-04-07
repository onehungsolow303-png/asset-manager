"""
Shared State — The central data layer that all agents read from and write to.
Maintains the map's current state as numpy arrays (grid layers) and lists (entities, paths, labels).
Supports multiple z-levels for layered maps (dungeons, multi-floor buildings).
"""

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np


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
class ZLevel:
    """A single vertical layer of the map."""
    z: int
    width: int = 0
    height: int = 0
    terrain_color: np.ndarray = None
    walkability: np.ndarray = None
    structure_mask: np.ndarray = None
    water_mask: np.ndarray = None
    elevation: np.ndarray = None
    moisture: np.ndarray = None
    entities: list = field(default_factory=list)
    labels: list = field(default_factory=list)

    def __post_init__(self):
        h, w = self.height, self.width
        if h > 0 and w > 0:
            if self.terrain_color is None:
                self.terrain_color = np.zeros((h, w, 3), dtype=np.uint8)
            if self.walkability is None:
                self.walkability = np.ones((h, w), dtype=bool)
            if self.structure_mask is None:
                self.structure_mask = np.zeros((h, w), dtype=bool)
            if self.water_mask is None:
                self.water_mask = np.zeros((h, w), dtype=bool)
            if self.elevation is None:
                self.elevation = np.zeros((h, w), dtype=np.float32)
            if self.moisture is None:
                self.moisture = np.zeros((h, w), dtype=np.float32)


@dataclass
class Transition:
    """A link between two z-levels (stairs, ladder, trapdoor)."""
    x: int
    y: int
    from_z: int
    to_z: int
    transition_type: str  # "stairs_up", "stairs_down", "ladder", "trapdoor", "entrance"


@dataclass
class SpawnPoint:
    """A creature spawn location for the playtest viewer."""
    x: int
    y: int
    z: int
    token_type: str       # "player", "enemy", "npc"
    name: str
    stats: dict = field(default_factory=dict)
    ai_behavior: str = "static"  # "patrol", "guard", "chase", "static"


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

    Supports multiple z-levels via self.levels dict. The ground level (z=0) is
    always present. Backwards-compatible properties map attribute access
    (e.g. self.terrain_color) to the ground level so existing agents work unchanged.
    """

    def __init__(self, config: MapConfig):
        self.config = config
        self.rng = np.random.default_rng(config.seed)

        w, h = config.width, config.height

        # Create ground z-level and store in levels dict
        ground = ZLevel(z=0, width=w, height=h)
        self.levels: dict[int, ZLevel] = {0: ground}

        # Entity lists (paths are not per-level, they span the ground)
        self.paths: list[PathSegment] = []

        # Transitions between z-levels and spawn points
        self.transitions: list[Transition] = []
        self.spawns: list[SpawnPoint] = []

        # Generation metadata
        self.metadata: dict[str, Any] = {
            "generation_seed": config.seed,
            "map_type": config.map_type,
            "created_at": time.time(),
            "agents_completed": [],
        }

        # Pipeline fields (populated by generation pipeline agents)
        self.cave_mask: np.ndarray | None = None
        self.natural_openings: list[tuple[int, int, int, int]] = []  # (x, y, w, h)
        self.room_graph = None  # RoomGraph, set by TopologyAgent

    # ------------------------------------------------------------------
    # Ground-level backwards-compat properties
    # All existing agents write to shared_state.terrain_color etc. — these
    # transparently proxy to self.levels[0].
    # ------------------------------------------------------------------

    @property
    def terrain_color(self) -> np.ndarray:
        return self.levels[0].terrain_color

    @terrain_color.setter
    def terrain_color(self, value: np.ndarray):
        self.levels[0].terrain_color = value

    @property
    def walkability(self) -> np.ndarray:
        return self.levels[0].walkability

    @walkability.setter
    def walkability(self, value: np.ndarray):
        self.levels[0].walkability = value

    @property
    def structure_mask(self) -> np.ndarray:
        return self.levels[0].structure_mask

    @structure_mask.setter
    def structure_mask(self, value: np.ndarray):
        self.levels[0].structure_mask = value

    @property
    def water_mask(self) -> np.ndarray:
        return self.levels[0].water_mask

    @water_mask.setter
    def water_mask(self, value: np.ndarray):
        self.levels[0].water_mask = value

    @property
    def elevation(self) -> np.ndarray:
        return self.levels[0].elevation

    @elevation.setter
    def elevation(self, value: np.ndarray):
        self.levels[0].elevation = value

    @property
    def moisture(self) -> np.ndarray:
        return self.levels[0].moisture

    @moisture.setter
    def moisture(self, value: np.ndarray):
        self.levels[0].moisture = value

    @property
    def entities(self) -> list:
        return self.levels[0].entities

    @entities.setter
    def entities(self, value: list):
        self.levels[0].entities = value

    @property
    def labels(self) -> list:
        return self.levels[0].labels

    @labels.setter
    def labels(self, value: list):
        self.levels[0].labels = value

    # ------------------------------------------------------------------
    # Z-level management
    # ------------------------------------------------------------------

    def add_zlevel(self, z: int) -> ZLevel:
        """Create and register a new z-level. Returns it. Reuses existing if present."""
        if z in self.levels:
            return self.levels[z]
        level = ZLevel(
            z=z,
            width=self.config.width,
            height=self.config.height,
        )
        self.levels[z] = level
        return level

    def add_transition(self, t: Transition):
        """Register a transition between z-levels."""
        self.transitions.append(t)

    @property
    def z_range(self) -> tuple[int, int]:
        """Return (min_z, max_z) across all registered levels."""
        keys = self.levels.keys()
        return (min(keys), max(keys))

    # ------------------------------------------------------------------
    # Existing public API (unchanged behaviour)
    # ------------------------------------------------------------------

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
            "z_levels": len(self.levels),
            "z_range": self.z_range,
            "transitions": len(self.transitions),
            "spawns": len(self.spawns),
        }

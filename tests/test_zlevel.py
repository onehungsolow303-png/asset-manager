"""Tests for ZLevel, Transition, SpawnPoint dataclasses and SharedState z-level support."""

import sys
import os
import numpy as np
import pytest

# Add mapgen_agents to path so imports resolve the same way the agents use them.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import (
    ZLevel, Transition, SpawnPoint,
    SharedState, MapConfig, Entity, Label,
)


# ------------------------------------------------------------------
# ZLevel dataclass
# ------------------------------------------------------------------

class TestZLevel:
    def test_creation_with_dimensions(self):
        """ZLevel should auto-init all arrays to correct shapes when w/h given."""
        zl = ZLevel(z=0, width=64, height=32)
        assert zl.terrain_color.shape == (32, 64, 3)
        assert zl.terrain_color.dtype == np.uint8
        assert zl.walkability.shape == (32, 64)
        assert zl.walkability.dtype == bool
        assert zl.walkability.all()  # default walkable
        assert zl.structure_mask.shape == (32, 64)
        assert not zl.structure_mask.any()
        assert zl.water_mask.shape == (32, 64)
        assert not zl.water_mask.any()
        assert zl.elevation.shape == (32, 64)
        assert zl.elevation.dtype == np.float32
        assert zl.moisture.shape == (32, 64)
        assert zl.moisture.dtype == np.float32
        assert zl.entities == []
        assert zl.labels == []

    def test_creation_without_dimensions(self):
        """ZLevel with no w/h should leave arrays as None."""
        zl = ZLevel(z=-1)
        assert zl.terrain_color is None
        assert zl.walkability is None

    def test_z_value_stored(self):
        zl = ZLevel(z=3, width=8, height=8)
        assert zl.z == 3

    def test_custom_array_not_overwritten(self):
        """If caller passes a pre-built array, __post_init__ should keep it."""
        custom = np.full((16, 16, 3), 128, dtype=np.uint8)
        zl = ZLevel(z=0, width=16, height=16, terrain_color=custom)
        assert zl.terrain_color is custom
        assert (zl.terrain_color == 128).all()


# ------------------------------------------------------------------
# Transition dataclass
# ------------------------------------------------------------------

class TestTransition:
    def test_creation(self):
        t = Transition(x=10, y=20, from_z=0, to_z=-1, transition_type="stairs_down")
        assert t.x == 10
        assert t.y == 20
        assert t.from_z == 0
        assert t.to_z == -1
        assert t.transition_type == "stairs_down"

    def test_all_types(self):
        for tt in ("stairs_up", "stairs_down", "ladder", "trapdoor", "entrance"):
            t = Transition(x=0, y=0, from_z=0, to_z=1, transition_type=tt)
            assert t.transition_type == tt


# ------------------------------------------------------------------
# SpawnPoint dataclass
# ------------------------------------------------------------------

class TestSpawnPoint:
    def test_creation_defaults(self):
        sp = SpawnPoint(x=5, y=6, z=0, token_type="player", name="Hero")
        assert sp.x == 5
        assert sp.y == 6
        assert sp.z == 0
        assert sp.token_type == "player"
        assert sp.name == "Hero"
        assert sp.stats == {}
        assert sp.ai_behavior == "static"

    def test_creation_with_stats(self):
        sp = SpawnPoint(
            x=1, y=2, z=-1, token_type="enemy", name="Goblin",
            stats={"hp": 10, "ac": 12}, ai_behavior="patrol",
        )
        assert sp.stats["hp"] == 10
        assert sp.ai_behavior == "patrol"


# ------------------------------------------------------------------
# SharedState backwards compatibility
# ------------------------------------------------------------------

class TestSharedStateBackwardsCompat:
    def setup_method(self):
        self.cfg = MapConfig(width=64, height=32, seed=1)
        self.ss = SharedState(self.cfg)

    def test_terrain_color_read(self):
        assert self.ss.terrain_color.shape == (32, 64, 3)
        assert self.ss.terrain_color.dtype == np.uint8

    def test_terrain_color_write(self):
        self.ss.terrain_color[0, 0] = [255, 0, 0]
        assert (self.ss.levels[0].terrain_color[0, 0] == [255, 0, 0]).all()

    def test_terrain_color_setter(self):
        new_arr = np.ones((32, 64, 3), dtype=np.uint8) * 42
        self.ss.terrain_color = new_arr
        assert self.ss.levels[0].terrain_color is new_arr

    def test_walkability(self):
        assert self.ss.walkability.shape == (32, 64)
        assert self.ss.walkability.all()
        self.ss.walkability[0, 0] = False
        assert not self.ss.levels[0].walkability[0, 0]

    def test_elevation(self):
        assert self.ss.elevation.shape == (32, 64)
        self.ss.elevation[5, 5] = 0.75
        assert self.ss.levels[0].elevation[5, 5] == pytest.approx(0.75)

    def test_moisture(self):
        assert self.ss.moisture.shape == (32, 64)

    def test_water_mask(self):
        assert self.ss.water_mask.shape == (32, 64)
        assert not self.ss.water_mask.any()

    def test_structure_mask(self):
        assert self.ss.structure_mask.shape == (32, 64)
        assert not self.ss.structure_mask.any()

    def test_entities_list(self):
        assert self.ss.entities == []
        e = Entity(entity_type="tree", position=(1, 2))
        self.ss.entities.append(e)
        assert len(self.ss.levels[0].entities) == 1

    def test_labels_list(self):
        assert self.ss.labels == []
        lbl = Label(text="Town", position=(10, 10))
        self.ss.labels.append(lbl)
        assert len(self.ss.levels[0].labels) == 1

    def test_get_walkable_positions(self):
        self.ss.water_mask[0, 0] = True
        self.ss.structure_mask[0, 1] = True
        wp = self.ss.get_walkable_positions()
        assert not wp[0, 0]
        assert not wp[0, 1]
        assert wp[1, 1]

    def test_log_agent_completion(self):
        self.ss.log_agent_completion("TerrainAgent")
        assert self.ss.metadata["agents_completed"][-1]["agent"] == "TerrainAgent"


# ------------------------------------------------------------------
# SharedState z-level management
# ------------------------------------------------------------------

class TestSharedStateZLevels:
    def setup_method(self):
        self.cfg = MapConfig(width=32, height=32, seed=7)
        self.ss = SharedState(self.cfg)

    def test_ground_level_exists(self):
        assert 0 in self.ss.levels
        assert self.ss.levels[0].z == 0

    def test_add_zlevel_new(self):
        zl = self.ss.add_zlevel(-1)
        assert zl.z == -1
        assert zl.width == 32
        assert zl.height == 32
        assert zl.terrain_color.shape == (32, 32, 3)
        assert -1 in self.ss.levels

    def test_add_zlevel_existing_returns_same(self):
        """Adding z=0 again should return the existing ground level, not overwrite."""
        original = self.ss.levels[0]
        returned = self.ss.add_zlevel(0)
        assert returned is original

    def test_z_range_single(self):
        assert self.ss.z_range == (0, 0)

    def test_z_range_multiple(self):
        self.ss.add_zlevel(-2)
        self.ss.add_zlevel(1)
        assert self.ss.z_range == (-2, 1)

    def test_transitions_list(self):
        assert self.ss.transitions == []
        t = Transition(x=5, y=5, from_z=0, to_z=-1, transition_type="stairs_down")
        self.ss.add_transition(t)
        assert len(self.ss.transitions) == 1
        assert self.ss.transitions[0] is t

    def test_spawns_list(self):
        assert self.ss.spawns == []
        sp = SpawnPoint(x=1, y=1, z=0, token_type="player", name="P1")
        self.ss.spawns.append(sp)
        assert len(self.ss.spawns) == 1

    def test_summary_includes_zlevel_info(self):
        self.ss.add_zlevel(-1)
        t = Transition(x=0, y=0, from_z=0, to_z=-1, transition_type="stairs_down")
        self.ss.add_transition(t)
        self.ss.spawns.append(SpawnPoint(x=0, y=0, z=0, token_type="player", name="P"))
        s = self.ss.summary()
        assert s["z_levels"] == 2
        assert s["z_range"] == (-1, 0)
        assert s["transitions"] == 1
        assert s["spawns"] == 1

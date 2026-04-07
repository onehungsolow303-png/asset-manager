"""Tests for TerrainAgent pipeline enhancements."""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from agents.terrain_agent import TerrainAgent, BIOME_PRESETS


class TestNewBiomePresets:
    def test_flat_floor_preset_exists(self):
        assert "flat_floor" in BIOME_PRESETS

    def test_flat_floor_produces_flat_elevation(self):
        config = MapConfig(width=64, height=64, biome="flat_floor", map_type="tavern", seed=42)
        state = SharedState(config)
        agent = TerrainAgent()
        agent.execute(state, {"biome": "flat_floor"})
        assert state.elevation.std() < 0.05
        assert state.walkability.mean() > 0.95

    def test_road_ready_preset_exists(self):
        assert "road_ready" in BIOME_PRESETS


class TestRawNoiseExposure:
    def test_raw_elevation_stored_in_metadata(self):
        config = MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42)
        state = SharedState(config)
        agent = TerrainAgent()
        agent.execute(state, {"biome": "forest"})
        assert "raw_elevation" in state.metadata
        assert isinstance(state.metadata["raw_elevation"], np.ndarray)
        assert state.metadata["raw_elevation"].shape == (64, 64)

    def test_raw_elevation_is_pre_modification(self):
        config = MapConfig(width=64, height=64, biome="cave", map_type="cave", seed=42)
        state = SharedState(config)
        agent = TerrainAgent()
        agent.execute(state, {"biome": "cave"})
        raw = state.metadata["raw_elevation"]
        assert raw.min() >= 0.0
        assert raw.max() <= 1.0
        assert raw.std() > 0.05  # not flat

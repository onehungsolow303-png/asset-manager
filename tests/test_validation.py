"""Tests for pipeline phase validation functions."""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from pipeline.validation import validate_terrain, ValidationResult


class TestValidationResult:
    def test_passed(self):
        r = ValidationResult(passed=True, errors=[])
        assert r.passed is True
        assert r.errors == []

    def test_failed(self):
        r = ValidationResult(passed=False, errors=["not enough walkable area"])
        assert r.passed is False
        assert len(r.errors) == 1


class TestValidateTerrain:
    def test_good_terrain_passes(self):
        config = MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42)
        state = SharedState(config)
        state.walkability[:] = True
        state.water_mask[:] = False
        result = validate_terrain(state, family="settlement", min_walkable_pct=0.2)
        assert result.passed is True

    def test_insufficient_walkable_area_fails(self):
        config = MapConfig(width=64, height=64, biome="dungeon", map_type="dungeon", seed=42)
        state = SharedState(config)
        state.walkability[:] = False
        result = validate_terrain(state, family="underground", min_walkable_pct=0.1)
        assert result.passed is False
        assert any("walkable" in e.lower() for e in result.errors)

    def test_cave_mask_has_open_space(self):
        config = MapConfig(width=64, height=64, biome="dungeon", map_type="dungeon", seed=42)
        state = SharedState(config)
        state.walkability[:] = True
        state.cave_mask = np.zeros((64, 64), dtype=bool)
        result = validate_terrain(state, family="underground", min_walkable_pct=0.1)
        assert result.passed is False
        assert any("cave" in e.lower() for e in result.errors)

    def test_cave_mask_not_checked_for_settlements(self):
        config = MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42)
        state = SharedState(config)
        state.walkability[:] = True
        state.cave_mask = None
        result = validate_terrain(state, family="settlement", min_walkable_pct=0.1)
        assert result.passed is True

    def test_missing_cave_mask_fails_for_underground(self):
        config = MapConfig(width=64, height=64, biome="dungeon", map_type="dungeon", seed=42)
        state = SharedState(config)
        state.walkability[:] = True
        state.cave_mask = None  # should have been set by CaveCarver
        result = validate_terrain(state, family="underground", min_walkable_pct=0.1)
        assert result.passed is False
        assert any("cave" in e.lower() for e in result.errors)

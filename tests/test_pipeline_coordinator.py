"""Tests for PipelineCoordinator — 3-phase orchestration with validation."""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from pipeline.coordinator import PipelineCoordinator
from pipeline.generation_request import GenerationRequest
from shared_state import SharedState


class TestPipelineCoordinatorInit:
    def test_creates_shared_state(self):
        req = GenerationRequest(
            map_type="dungeon", biome="dungeon", size="standard", seed=42,
            party_level=5, party_size=4,
        )
        coord = PipelineCoordinator(req)
        assert coord.request is req
        assert coord.profile["family"] == "underground"
        assert coord.family == "underground"

    def test_resolves_biome_override(self):
        req = GenerationRequest(
            map_type="dungeon", biome="forest", size="standard", seed=42,
        )
        coord = PipelineCoordinator(req)
        assert coord.effective_biome == "dungeon"

    def test_no_biome_override(self):
        req = GenerationRequest(
            map_type="village", biome="forest", size="standard", seed=42,
        )
        coord = PipelineCoordinator(req)
        assert coord.effective_biome == "forest"


class TestPhase1Execution:
    def test_phase1_produces_terrain(self):
        req = GenerationRequest(
            map_type="village", biome="forest", size="small_encounter", seed=42,
        )
        coord = PipelineCoordinator(req)
        result = coord.run_phase1()
        assert result.passed is True
        state = coord.shared_state
        assert state.elevation is not None
        assert state.moisture is not None
        assert state.terrain_color is not None

    def test_phase1_runs_cave_carver_for_underground(self):
        req = GenerationRequest(
            map_type="dungeon", biome="dungeon", size="small_encounter", seed=42,
        )
        coord = PipelineCoordinator(req)
        result = coord.run_phase1()
        assert result.passed is True
        assert coord.shared_state.cave_mask is not None

    def test_phase1_skips_cave_carver_for_interior(self):
        req = GenerationRequest(
            map_type="tavern", biome="forest", size="small_encounter", seed=42,
        )
        coord = PipelineCoordinator(req)
        result = coord.run_phase1()
        assert result.passed is True
        assert coord.shared_state.cave_mask is None

    def test_phase1_uses_flat_floor_for_interior(self):
        req = GenerationRequest(
            map_type="tavern", biome="forest", size="small_encounter", seed=42,
        )
        coord = PipelineCoordinator(req)
        result = coord.run_phase1()
        assert result.passed is True
        assert coord.shared_state.elevation.std() < 0.05


class TestFullPipeline:
    def test_generate_returns_shared_state(self):
        req = GenerationRequest(
            map_type="dungeon", biome="dungeon", size="small_encounter", seed=42,
            party_level=3, party_size=4,
        )
        coord = PipelineCoordinator(req)
        state = coord.generate()
        assert isinstance(state, SharedState)
        assert state.config.map_type == "dungeon"
        assert state.config.seed == 42

    def test_deterministic_generation(self):
        req1 = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=42)
        req2 = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=42)
        state1 = PipelineCoordinator(req1).generate()
        state2 = PipelineCoordinator(req2).generate()
        np.testing.assert_array_equal(state1.elevation, state2.elevation)

    def test_different_seeds_produce_different_maps(self):
        req1 = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=42)
        req2 = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=999)
        state1 = PipelineCoordinator(req1).generate()
        state2 = PipelineCoordinator(req2).generate()
        assert not np.array_equal(state1.elevation, state2.elevation)

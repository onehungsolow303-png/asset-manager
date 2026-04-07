"""Tests for CaveCarverAgent — noise-threshold carving + cellular automata."""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from agents.terrain_agent import TerrainAgent
from agents.cave_carver_agent import CaveCarverAgent


def make_state_with_terrain(biome="dungeon", map_type="dungeon", seed=42, size=128):
    config = MapConfig(width=size, height=size, biome=biome, map_type=map_type, seed=seed)
    state = SharedState(config)
    TerrainAgent().execute(state, {"biome": biome})
    return state


class TestCaveCarverBasics:
    def test_produces_cave_mask(self):
        state = make_state_with_terrain()
        CaveCarverAgent().execute(state, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        assert state.cave_mask is not None
        assert state.cave_mask.shape == (128, 128)
        assert state.cave_mask.dtype == bool

    def test_cave_mask_has_open_space(self):
        state = make_state_with_terrain()
        CaveCarverAgent().execute(state, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        open_pct = state.cave_mask.mean()
        assert open_pct > 0.05
        assert open_pct < 0.95

    def test_natural_openings_detected(self):
        state = make_state_with_terrain()
        CaveCarverAgent().execute(state, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        assert isinstance(state.natural_openings, list)
        assert len(state.natural_openings) >= 1

    def test_natural_openings_format(self):
        state = make_state_with_terrain()
        CaveCarverAgent().execute(state, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        for opening in state.natural_openings:
            assert len(opening) == 4
            x, y, w, h = opening
            assert w > 0 and h > 0


class TestCaveCarverConnectivity:
    def test_single_connected_region(self):
        state = make_state_with_terrain(seed=42)
        CaveCarverAgent().execute(state, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        mask = state.cave_mask.copy()
        open_tiles = np.argwhere(mask)
        if len(open_tiles) == 0:
            pytest.skip("No open tiles carved")
        start_y, start_x = open_tiles[0]
        visited = np.zeros_like(mask)
        stack = [(start_y, start_x)]
        visited[start_y, start_x] = True
        count = 0
        while stack:
            cy, cx = stack.pop()
            count += 1
            for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1]:
                    if mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        stack.append((ny, nx))
        total_open = mask.sum()
        assert count == total_open, f"Expected single region ({total_open} tiles), flood fill found {count}"


class TestCaveCarverSmoothing:
    def test_smoothing_reduces_isolated_pixels(self):
        state = make_state_with_terrain(seed=100)
        CaveCarverAgent().execute(state, {
            "carve_threshold": 0.45, "passage_threshold": 0.50, "smoothing_iterations": 3,
        })
        mask = state.cave_mask
        isolated = 0
        h, w = mask.shape
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if mask[y, x]:
                    neighbors_open = mask[y-1, x] + mask[y+1, x] + mask[y, x-1] + mask[y, x+1]
                    if neighbors_open == 0:
                        isolated += 1
        assert isolated == 0


class TestCaveCarverSkip:
    def test_skip_when_not_needed(self):
        state = make_state_with_terrain(biome="forest", map_type="village")
        result = CaveCarverAgent().execute(state, {"skip": True})
        assert state.cave_mask is None
        assert result["details"]["skipped"] is True


class TestCaveCarverDeterminism:
    def test_same_seed_same_result(self):
        state1 = make_state_with_terrain(seed=42)
        state2 = make_state_with_terrain(seed=42)
        CaveCarverAgent().execute(state1, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        CaveCarverAgent().execute(state2, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        np.testing.assert_array_equal(state1.cave_mask, state2.cave_mask)

    def test_different_seed_different_result(self):
        state1 = make_state_with_terrain(seed=42)
        state2 = make_state_with_terrain(seed=999)
        CaveCarverAgent().execute(state1, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        CaveCarverAgent().execute(state2, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        assert not np.array_equal(state1.cave_mask, state2.cave_mask)

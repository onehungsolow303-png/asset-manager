"""Tests for GenerationRequest dataclass."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from pipeline.generation_request import GenerationRequest


class TestGenerationRequest:
    def test_creation_with_all_fields(self):
        req = GenerationRequest(
            map_type="dungeon",
            biome="dungeon",
            size="standard",
            seed=42,
            party_level=5,
            party_size=4,
            output_dir="./output",
            unity_export=True,
        )
        assert req.map_type == "dungeon"
        assert req.biome == "dungeon"
        assert req.size == "standard"
        assert req.seed == 42
        assert req.party_level == 5
        assert req.party_size == 4
        assert req.output_dir == "./output"
        assert req.unity_export is True

    def test_defaults(self):
        req = GenerationRequest(map_type="village", biome="forest", size="standard", seed=1)
        assert req.party_level == 3
        assert req.party_size == 4
        assert req.output_dir == "./output"
        assert req.unity_export is False

    def test_party_level_bounds(self):
        with pytest.raises(ValueError, match="party_level"):
            GenerationRequest(map_type="dungeon", biome="dungeon", size="standard", seed=1, party_level=0)
        with pytest.raises(ValueError, match="party_level"):
            GenerationRequest(map_type="dungeon", biome="dungeon", size="standard", seed=1, party_level=21)

    def test_valid_size_presets(self):
        for size in ["small_encounter", "medium_encounter", "large_encounter", "standard", "large", "region", "open_world"]:
            req = GenerationRequest(map_type="dungeon", biome="dungeon", size=size, seed=1)
            assert req.size == size

    def test_invalid_size(self):
        with pytest.raises(ValueError, match="size"):
            GenerationRequest(map_type="dungeon", biome="dungeon", size="tiny", seed=1)

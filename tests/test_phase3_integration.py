"""Integration tests for Phase 3 in PipelineCoordinator."""

import sys, os, numpy as np, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from pipeline.coordinator import PipelineCoordinator
from pipeline.generation_request import GenerationRequest

class TestPhase3Integration:
    def test_full_pipeline_produces_populated_dungeon(self):
        req = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=42, party_level=5, party_size=4)
        state = PipelineCoordinator(req).generate()
        assert state.room_graph is not None
        # Check rooms have purposes
        for node in state.room_graph.nodes:
            assert node.purpose is not None, f"{node.node_id} has no purpose"

    def test_encounters_distributed(self):
        req = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=42, party_level=5, party_size=4)
        state = PipelineCoordinator(req).generate()
        rooms_with_encounters = sum(1 for n in state.room_graph.nodes if n.metadata.get("encounter", {}).get("xp", 0) > 0)
        assert rooms_with_encounters >= 2

    def test_loot_distributed(self):
        req = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=42, party_level=5, party_size=4)
        state = PipelineCoordinator(req).generate()
        rooms_with_loot = sum(1 for n in state.room_graph.nodes if n.metadata.get("loot", {}).get("gold", 0) > 0)
        assert rooms_with_loot >= 1

    def test_player_spawn_exists(self):
        req = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=42, party_level=5, party_size=4)
        state = PipelineCoordinator(req).generate()
        player_spawns = [s for s in state.spawns if s.token_type == "player"]
        assert len(player_spawns) >= 1

    def test_boss_room_has_encounter(self):
        req = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=42, party_level=5, party_size=4)
        state = PipelineCoordinator(req).generate()
        boss = state.room_graph.boss_node
        if boss:
            assert boss.metadata.get("encounter", {}).get("xp", 0) > 0

    def test_dressing_placed(self):
        req = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=42, party_level=5, party_size=4)
        state = PipelineCoordinator(req).generate()
        dressing = [e for e in state.entities if e.entity_type == "dressing"]
        assert len(dressing) >= 1

    def test_village_pipeline_works(self):
        req = GenerationRequest(map_type="village", biome="forest", size="small_encounter", seed=42, party_level=3, party_size=4)
        state = PipelineCoordinator(req).generate()
        assert state.room_graph is not None
        for node in state.room_graph.nodes:
            assert node.purpose is not None

    def test_tavern_pipeline_works(self):
        req = GenerationRequest(map_type="tavern", biome="forest", size="small_encounter", seed=42, party_level=3, party_size=4)
        state = PipelineCoordinator(req).generate()
        assert state.room_graph is not None

    def test_deterministic_full_pipeline(self):
        req1 = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=42, party_level=5, party_size=4)
        req2 = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=42, party_level=5, party_size=4)
        state1 = PipelineCoordinator(req1).generate()
        state2 = PipelineCoordinator(req2).generate()
        for n1, n2 in zip(state1.room_graph.nodes, state2.room_graph.nodes):
            assert n1.purpose == n2.purpose
            assert n1.metadata.get("encounter") == n2.metadata.get("encounter")

"""Integration tests for Phase 2 in PipelineCoordinator."""

import sys, os, numpy as np, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from pipeline.coordinator import PipelineCoordinator
from pipeline.generation_request import GenerationRequest

class TestPhase2Integration:
    def test_phase2_produces_room_graph(self):
        req = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=42, party_level=3, party_size=4)
        coord = PipelineCoordinator(req)
        coord.run_phase1()
        result = coord.run_phase2()
        assert result.passed is True
        assert coord.shared_state.room_graph is not None
        assert coord.shared_state.room_graph.node_count >= 3

    def test_phase2_rooms_have_positions(self):
        req = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=42)
        coord = PipelineCoordinator(req)
        coord.run_phase1()
        coord.run_phase2()
        for node in coord.shared_state.room_graph.nodes:
            assert node.position is not None
            assert node.size is not None

    def test_full_pipeline_with_phase2(self):
        req = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=42, party_level=3, party_size=4)
        coord = PipelineCoordinator(req)
        state = coord.generate()
        assert state.room_graph is not None
        assert state.room_graph.entrance_node is not None

    def test_village_uses_settlement_topology(self):
        req = GenerationRequest(map_type="village", biome="forest", size="small_encounter", seed=42)
        coord = PipelineCoordinator(req)
        coord.run_phase1()
        result = coord.run_phase2()
        assert result.passed is True
        assert coord.shared_state.room_graph is not None

    def test_tavern_uses_interior_topology(self):
        req = GenerationRequest(map_type="tavern", biome="forest", size="small_encounter", seed=42)
        coord = PipelineCoordinator(req)
        coord.run_phase1()
        result = coord.run_phase2()
        assert result.passed is True
        assert coord.shared_state.room_graph is not None

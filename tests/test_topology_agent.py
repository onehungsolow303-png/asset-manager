"""Tests for TopologyAgent — abstract room graph generation."""

import sys, os, numpy as np, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from agents.topology_agent import TopologyAgent
from data.room_graph import RoomGraph, RoomNode, GraphEdge

def make_state(map_type="dungeon", seed=42, size=256):
    config = MapConfig(width=size, height=size, biome="dungeon", map_type=map_type, seed=seed)
    return SharedState(config)

class TestTopologySelection:
    def test_selects_from_profile_preference(self):
        state = make_state()
        agent = TopologyAgent()
        result = agent.execute(state, {"topology_preference": ["hub_and_spoke", "loop_based"], "size_topology_override": {}, "size": "standard", "room_count": 10})
        assert result["status"] == "completed"
        assert state.room_graph is not None

    def test_size_override_forces_topology(self):
        state = make_state()
        agent = TopologyAgent()
        result = agent.execute(state, {"topology_preference": ["hub_and_spoke"], "size_topology_override": {"small_encounter": "linear_with_branches"}, "size": "small_encounter", "room_count": 5})
        assert result["status"] == "completed"
        assert state.room_graph.node_count == 5

class TestLinearTopology:
    def test_produces_correct_node_count(self):
        state = make_state()
        TopologyAgent().execute(state, {"topology_preference": ["linear_with_branches"], "size_topology_override": {}, "size": "standard", "room_count": 8})
        assert state.room_graph.node_count == 8

    def test_has_entrance_and_boss(self):
        state = make_state()
        TopologyAgent().execute(state, {"topology_preference": ["linear_with_branches"], "size_topology_override": {}, "size": "standard", "room_count": 6})
        graph = state.room_graph
        assert graph.entrance_node is not None
        assert graph.entrance_node.zone == 0

    def test_all_nodes_reachable(self):
        state = make_state()
        TopologyAgent().execute(state, {"topology_preference": ["linear_with_branches"], "size_topology_override": {}, "size": "standard", "room_count": 8})
        graph = state.room_graph
        assert graph.all_reachable_from(graph.entrance_node.node_id)

    def test_zones_increase_from_entrance(self):
        state = make_state()
        TopologyAgent().execute(state, {"topology_preference": ["linear_with_branches"], "size_topology_override": {}, "size": "standard", "room_count": 8})
        graph = state.room_graph
        assert graph.entrance_node.zone == 0
        assert graph.max_zone >= 1

    def test_deterministic_with_same_seed(self):
        state1, state2 = make_state(seed=42), make_state(seed=42)
        params = {"topology_preference": ["linear_with_branches"], "size_topology_override": {}, "size": "standard", "room_count": 8}
        TopologyAgent().execute(state1, params)
        TopologyAgent().execute(state2, params)
        assert state1.room_graph.node_count == state2.room_graph.node_count
        assert state1.room_graph.edge_count == state2.room_graph.edge_count

class TestLoopTopology:
    def test_produces_cycles(self):
        state = make_state()
        TopologyAgent().execute(state, {"topology_preference": ["loop_based"], "size_topology_override": {}, "size": "standard", "room_count": 10})
        graph = state.room_graph
        assert graph.edge_count > graph.node_count - 1

    def test_all_nodes_reachable(self):
        state = make_state()
        TopologyAgent().execute(state, {"topology_preference": ["loop_based"], "size_topology_override": {}, "size": "standard", "room_count": 10})
        assert state.room_graph.all_reachable_from(state.room_graph.entrance_node.node_id)

class TestHubAndSpokeTopology:
    def test_has_hub_node(self):
        state = make_state()
        TopologyAgent().execute(state, {"topology_preference": ["hub_and_spoke"], "size_topology_override": {}, "size": "standard", "room_count": 10})
        graph = state.room_graph
        max_degree = max(len(graph.neighbors(n.node_id)) for n in graph.nodes)
        assert max_degree >= 3

    def test_all_nodes_reachable(self):
        state = make_state()
        TopologyAgent().execute(state, {"topology_preference": ["hub_and_spoke"], "size_topology_override": {}, "size": "standard", "room_count": 10})
        assert state.room_graph.all_reachable_from(state.room_graph.entrance_node.node_id)

class TestHybridTopology:
    def test_has_hub_and_cycles(self):
        state = make_state()
        TopologyAgent().execute(state, {"topology_preference": ["hybrid"], "size_topology_override": {}, "size": "standard", "room_count": 12})
        graph = state.room_graph
        max_degree = max(len(graph.neighbors(n.node_id)) for n in graph.nodes)
        assert max_degree >= 3
        assert graph.edge_count > graph.node_count - 1

    def test_all_nodes_reachable(self):
        state = make_state()
        TopologyAgent().execute(state, {"topology_preference": ["hybrid"], "size_topology_override": {}, "size": "standard", "room_count": 12})
        assert state.room_graph.all_reachable_from(state.room_graph.entrance_node.node_id)

class TestZoneAssignment:
    def test_entrance_is_zone_0(self):
        state = make_state()
        TopologyAgent().execute(state, {"topology_preference": ["linear_with_branches"], "size_topology_override": {}, "size": "standard", "room_count": 8})
        assert state.room_graph.entrance_node.zone == 0

    def test_zones_are_contiguous(self):
        state = make_state()
        TopologyAgent().execute(state, {"topology_preference": ["hub_and_spoke"], "size_topology_override": {}, "size": "standard", "room_count": 10})
        zones = sorted(set(n.zone for n in state.room_graph.nodes))
        assert zones[0] == 0
        for i in range(1, len(zones)):
            assert zones[i] - zones[i-1] <= 1

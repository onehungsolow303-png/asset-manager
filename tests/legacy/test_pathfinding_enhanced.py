"""Tests for PathfindingAgent connectivity validation mode."""

import sys, os, numpy as np, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from agents.pathfinding_agent import PathfindingAgent
from data.room_graph import RoomGraph, RoomNode, GraphEdge

def make_connected_state():
    config = MapConfig(width=128, height=128, biome="dungeon", map_type="dungeon", seed=42)
    state = SharedState(config)
    state.walkability[:] = False
    state.walkability[20:40, 20:50] = True  # Room A
    state.walkability[20:40, 60:90] = True  # Room B
    state.walkability[28:32, 50:60] = True  # Corridor
    graph = RoomGraph()
    graph.add_node(RoomNode("a", zone=0, tags={"entrance"}, position=(20, 20), size=(30, 20)))
    graph.add_node(RoomNode("b", zone=1, position=(60, 20), size=(30, 20)))
    graph.add_edge(GraphEdge("a", "b", "corridor"))
    state.room_graph = graph
    return state

def make_disconnected_state():
    config = MapConfig(width=128, height=128, biome="dungeon", map_type="dungeon", seed=42)
    state = SharedState(config)
    state.walkability[:] = False
    state.walkability[20:40, 20:50] = True
    state.walkability[80:100, 80:110] = True
    graph = RoomGraph()
    graph.add_node(RoomNode("a", zone=0, tags={"entrance"}, position=(20, 20), size=(30, 20)))
    graph.add_node(RoomNode("b", zone=1, position=(80, 80), size=(30, 20)))
    graph.add_edge(GraphEdge("a", "b", "corridor"))
    state.room_graph = graph
    return state

class TestValidateConnectivity:
    def test_connected_rooms_pass(self):
        state = make_connected_state()
        result = PathfindingAgent().execute(state, {"mode": "validate"})
        assert result["status"] == "completed"
        assert result["details"]["all_connected"] is True
        assert result["details"]["orphaned_rooms"] == []

    def test_disconnected_rooms_detected(self):
        state = make_disconnected_state()
        result = PathfindingAgent().execute(state, {"mode": "validate"})
        assert result["status"] == "completed"
        assert result["details"]["all_connected"] is False
        assert len(result["details"]["orphaned_rooms"]) > 0

    def test_no_graph_returns_trivially_connected(self):
        config = MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42)
        state = SharedState(config)
        result = PathfindingAgent().execute(state, {"mode": "validate"})
        assert result["status"] == "completed"
        assert result["details"]["all_connected"] is True

    def test_existing_road_generation_still_works(self):
        config = MapConfig(width=256, height=256, biome="forest", map_type="village", seed=42)
        state = SharedState(config)
        # Need walkable terrain for road generation
        state.walkability[:] = True
        result = PathfindingAgent().execute(state, {"road_density": "low"})
        assert result["status"] == "completed"

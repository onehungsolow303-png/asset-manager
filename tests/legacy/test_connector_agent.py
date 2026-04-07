"""Tests for ConnectorAgent — corridors, doors, stairs."""

import sys, os, numpy as np, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig, Entity, Transition
from agents.connector_agent import ConnectorAgent
from data.room_graph import RoomGraph, RoomNode, GraphEdge

def make_state_with_rooms():
    config = MapConfig(width=128, height=128, biome="dungeon", map_type="dungeon", seed=42)
    state = SharedState(config)
    state.walkability[:] = False
    state.terrain_color[:] = (40, 38, 35)
    # Carve two rooms
    state.walkability[20:40, 20:50] = True
    state.walkability[70:90, 60:90] = True
    graph = RoomGraph()
    graph.add_node(RoomNode("room_a", zone=0, position=(20, 20), size=(30, 20)))
    graph.add_node(RoomNode("room_b", zone=1, position=(60, 70), size=(30, 20)))
    graph.add_edge(GraphEdge("room_a", "room_b", "corridor"))
    state.room_graph = graph
    return state

class TestCorridorCarving:
    def test_corridor_connects_rooms(self):
        state = make_state_with_rooms()
        ConnectorAgent().execute(state, {"corridor_style": "carved", "door_frequency": 0.0})
        mid_y = 55
        walkable_at_mid = state.walkability[mid_y, :].sum()
        assert walkable_at_mid > 0, "Corridor should carve walkable tiles between rooms"

    def test_creates_path_segments(self):
        state = make_state_with_rooms()
        ConnectorAgent().execute(state, {"corridor_style": "carved", "door_frequency": 0.0})
        assert len(state.paths) >= 1

class TestDoorPlacement:
    def test_doors_placed_for_door_edges(self):
        state = make_state_with_rooms()
        state.room_graph._edges[0].connection_type = "door"
        ConnectorAgent().execute(state, {"corridor_style": "carved", "door_frequency": 1.0})
        doors = [e for e in state.entities if e.entity_type == "door"]
        assert len(doors) >= 1

class TestStairGeneration:
    def test_stairs_created_for_stairs_edge(self):
        config = MapConfig(width=128, height=128, biome="dungeon", map_type="dungeon", seed=42)
        state = SharedState(config)
        state.walkability[:] = False
        state.walkability[20:40, 20:50] = True
        state.walkability[70:90, 60:90] = True
        graph = RoomGraph()
        graph.add_node(RoomNode("room_a", zone=0, position=(20, 20), size=(30, 20)))
        graph.add_node(RoomNode("room_b", zone=1, position=(60, 70), size=(30, 20)))
        graph.add_edge(GraphEdge("room_a", "room_b", "stairs"))
        state.room_graph = graph
        ConnectorAgent().execute(state, {"corridor_style": "carved", "door_frequency": 0.0})
        assert len(state.transitions) >= 1
        assert state.transitions[0].transition_type in ("stairs_up", "stairs_down")

class TestConnectorDeterminism:
    def test_same_seed_same_result(self):
        state1, state2 = make_state_with_rooms(), make_state_with_rooms()
        params = {"corridor_style": "carved", "door_frequency": 0.5}
        ConnectorAgent().execute(state1, params)
        ConnectorAgent().execute(state2, params)
        np.testing.assert_array_equal(state1.walkability, state2.walkability)

class TestSkipMode:
    def test_skip_with_no_graph(self):
        config = MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42)
        state = SharedState(config)
        result = ConnectorAgent().execute(state, {"corridor_style": "road", "door_frequency": 0.0})
        assert result["status"] == "completed"

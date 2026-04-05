# tests/test_room_purpose_agent.py
"""Tests for RoomPurposeAgent — room role assignment."""

import sys, os, numpy as np, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from agents.room_purpose_agent import RoomPurposeAgent
from data.room_graph import RoomGraph, RoomNode, GraphEdge

def make_state_with_graph(room_count=6, seed=42):
    config = MapConfig(width=256, height=256, biome="dungeon", map_type="dungeon", seed=seed)
    state = SharedState(config)
    graph = RoomGraph()
    for i in range(room_count):
        tags = set()
        if i == 0: tags.add("entrance")
        if i == room_count - 1: tags.add("boss")
        graph.add_node(RoomNode(f"room_{i}", zone=i % 3, tags=tags, position=(20 + i*40, 20), size=(30, 20)))
    for i in range(room_count - 1):
        graph.add_edge(GraphEdge(f"room_{i}", f"room_{i+1}", "corridor"))
    state.room_graph = graph
    return state

DUNGEON_PROFILE = {
    "family": "underground",
    "room_pool": {
        "required": ["entrance", "boss_lair"],
        "common": ["guard_room", "barracks", "armory", "storage", "cell"],
        "uncommon": ["shrine", "alchemy_lab", "library", "crypt"],
        "rare": ["treasure_vault", "secret_chamber", "portal_room"],
    },
}

class TestRoomPurposeAssignment:
    def test_all_rooms_get_purpose(self):
        state = make_state_with_graph()
        RoomPurposeAgent().execute(state, {"profile": DUNGEON_PROFILE})
        for node in state.room_graph.nodes:
            assert node.purpose is not None, f"{node.node_id} has no purpose"

    def test_entrance_gets_entrance_purpose(self):
        state = make_state_with_graph()
        RoomPurposeAgent().execute(state, {"profile": DUNGEON_PROFILE})
        entrance = state.room_graph.entrance_node
        assert entrance.purpose == "entrance"

    def test_boss_gets_boss_lair_purpose(self):
        state = make_state_with_graph()
        RoomPurposeAgent().execute(state, {"profile": DUNGEON_PROFILE})
        boss = state.room_graph.boss_node
        assert boss.purpose == "boss_lair"

    def test_purposes_from_pool(self):
        state = make_state_with_graph()
        RoomPurposeAgent().execute(state, {"profile": DUNGEON_PROFILE})
        all_pool = (DUNGEON_PROFILE["room_pool"]["required"] +
                    DUNGEON_PROFILE["room_pool"]["common"] +
                    DUNGEON_PROFILE["room_pool"]["uncommon"] +
                    DUNGEON_PROFILE["room_pool"]["rare"])
        for node in state.room_graph.nodes:
            assert node.purpose in all_pool, f"{node.node_id} has unexpected purpose {node.purpose}"

    def test_deterministic(self):
        state1, state2 = make_state_with_graph(seed=42), make_state_with_graph(seed=42)
        RoomPurposeAgent().execute(state1, {"profile": DUNGEON_PROFILE})
        RoomPurposeAgent().execute(state2, {"profile": DUNGEON_PROFILE})
        for n1, n2 in zip(state1.room_graph.nodes, state2.room_graph.nodes):
            assert n1.purpose == n2.purpose

    def test_no_graph_skips(self):
        config = MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42)
        state = SharedState(config)
        result = RoomPurposeAgent().execute(state, {"profile": DUNGEON_PROFILE})
        assert result["status"] == "completed"

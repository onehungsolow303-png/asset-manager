# tests/test_encounter_agent.py
"""Tests for EncounterAgent — XP budget distribution with pacing."""

import sys, os, math, numpy as np, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from agents.encounter_agent import EncounterAgent
from data.room_graph import RoomGraph, RoomNode, GraphEdge

def make_state_with_purposes(room_count=8, seed=42):
    config = MapConfig(width=256, height=256, biome="dungeon", map_type="dungeon", seed=seed)
    state = SharedState(config)
    graph = RoomGraph()
    purposes = ["entrance", "guard_room", "storage", "barracks", "armory", "shrine", "guard_room", "boss_lair"]
    for i in range(room_count):
        tags = set()
        if i == 0: tags.add("entrance")
        if i == room_count - 1: tags.add("boss")
        node = RoomNode(f"room_{i}", zone=i * 2 // room_count, tags=tags, position=(20+i*30, 20), size=(25, 20))
        node.purpose = purposes[i] if i < len(purposes) else "storage"
        graph.add_node(node)
    for i in range(room_count - 1):
        graph.add_edge(GraphEdge(f"room_{i}", f"room_{i+1}", "corridor"))
    state.room_graph = graph
    return state

DUNGEON_PROFILE = {
    "family": "underground",
    "loot_tier": "medium",
    "creature_table": {
        "common": [("skeleton", 3), ("goblin", 2), ("rat", 2)],
        "uncommon": [("orc", 2), ("zombie", 1)],
        "boss": [("ogre", 1), ("troll", 1)],
    },
}

class TestEncounterBudget:
    def test_xp_distributed_within_budget(self):
        state = make_state_with_purposes()
        EncounterAgent().execute(state, {"profile": DUNGEON_PROFILE, "party_level": 5, "party_size": 4})
        total_xp = sum(n.metadata.get("encounter", {}).get("xp", 0) for n in state.room_graph.nodes)
        assert total_xp > 0, "Some XP should be distributed"

    def test_boss_room_gets_highest_xp(self):
        state = make_state_with_purposes()
        EncounterAgent().execute(state, {"profile": DUNGEON_PROFILE, "party_level": 5, "party_size": 4})
        boss = state.room_graph.boss_node
        boss_xp = boss.metadata.get("encounter", {}).get("xp", 0)
        for node in state.room_graph.nodes:
            if "boss" not in node.tags:
                node_xp = node.metadata.get("encounter", {}).get("xp", 0)
                assert boss_xp >= node_xp, f"Boss ({boss_xp}) should have >= XP than {node.node_id} ({node_xp})"

    def test_entrance_gets_low_xp(self):
        state = make_state_with_purposes()
        EncounterAgent().execute(state, {"profile": DUNGEON_PROFILE, "party_level": 5, "party_size": 4})
        entrance = state.room_graph.entrance_node
        entrance_xp = entrance.metadata.get("encounter", {}).get("xp", 0)
        avg_xp = np.mean([n.metadata.get("encounter", {}).get("xp", 0) for n in state.room_graph.nodes])
        assert entrance_xp <= avg_xp

    def test_some_rooms_are_empty(self):
        state = make_state_with_purposes()
        EncounterAgent().execute(state, {"profile": DUNGEON_PROFILE, "party_level": 5, "party_size": 4})
        empty = sum(1 for n in state.room_graph.nodes if n.metadata.get("encounter", {}).get("xp", 0) == 0)
        # At least 1 empty room for pacing
        assert empty >= 1

    def test_creatures_assigned(self):
        state = make_state_with_purposes()
        EncounterAgent().execute(state, {"profile": DUNGEON_PROFILE, "party_level": 5, "party_size": 4})
        rooms_with_creatures = sum(1 for n in state.room_graph.nodes if n.metadata.get("encounter", {}).get("creatures"))
        assert rooms_with_creatures >= 3

    def test_deterministic(self):
        state1, state2 = make_state_with_purposes(seed=42), make_state_with_purposes(seed=42)
        params = {"profile": DUNGEON_PROFILE, "party_level": 5, "party_size": 4}
        EncounterAgent().execute(state1, params)
        EncounterAgent().execute(state2, params)
        for n1, n2 in zip(state1.room_graph.nodes, state2.room_graph.nodes):
            assert n1.metadata.get("encounter") == n2.metadata.get("encounter")

    def test_no_graph_skips(self):
        config = MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42)
        state = SharedState(config)
        result = EncounterAgent().execute(state, {"profile": DUNGEON_PROFILE, "party_level": 3, "party_size": 4})
        assert result["status"] == "completed"

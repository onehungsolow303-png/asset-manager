# tests/test_loot_agent.py
"""Tests for LootAgent — three-pool risk-reward loot distribution."""

import sys, os, math, numpy as np, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from agents.loot_agent import LootAgent
from data.room_graph import RoomGraph, RoomNode, GraphEdge

def make_state_with_encounters(seed=42):
    config = MapConfig(width=256, height=256, biome="dungeon", map_type="dungeon", seed=seed)
    state = SharedState(config)
    graph = RoomGraph()
    rooms_data = [
        ("entrance", 0, {"entrance"}, "entrance", 0),
        ("guard1", 1, set(), "guard_room", 200),
        ("storage", 1, set(), "storage", 50),
        ("vault", 2, set(), "treasure_vault", 100),
        ("secret", 2, set(), "secret_chamber", 0),
        ("boss", 3, {"boss"}, "boss_lair", 800),
    ]
    for name, zone, tags, purpose, xp in rooms_data:
        node = RoomNode(name, zone=zone, tags=tags, position=(20, 20), size=(30, 20))
        node.purpose = purpose
        node.metadata["encounter"] = {"xp": xp, "creatures": []}
        node.metadata.setdefault("trap", None)
        graph.add_node(node)
    graph.add_edge(GraphEdge("entrance", "guard1", "corridor"))
    graph.add_edge(GraphEdge("guard1", "storage", "corridor"))
    graph.add_edge(GraphEdge("guard1", "vault", "corridor"))
    graph.add_edge(GraphEdge("storage", "secret", "secret"))
    graph.add_edge(GraphEdge("storage", "boss", "corridor"))
    state.room_graph = graph
    return state

DUNGEON_PROFILE = {"family": "underground", "loot_tier": "medium"}

class TestLootDistribution:
    def test_loot_distributed(self):
        state = make_state_with_encounters()
        LootAgent().execute(state, {"profile": DUNGEON_PROFILE, "party_level": 5, "party_size": 4})
        total_gold = sum(n.metadata.get("loot", {}).get("gold", 0) for n in state.room_graph.nodes)
        assert total_gold > 0

    def test_boss_gets_largest_share(self):
        state = make_state_with_encounters()
        LootAgent().execute(state, {"profile": DUNGEON_PROFILE, "party_level": 5, "party_size": 4})
        boss = state.room_graph.get_node("boss")
        boss_gold = boss.metadata.get("loot", {}).get("gold", 0)
        for node in state.room_graph.nodes:
            if "boss" not in node.tags:
                node_gold = node.metadata.get("loot", {}).get("gold", 0)
                assert boss_gold >= node_gold, f"Boss ({boss_gold}) should have >= gold than {node.node_id} ({node_gold})"

    def test_treasure_vault_has_items(self):
        state = make_state_with_encounters()
        LootAgent().execute(state, {"profile": DUNGEON_PROFILE, "party_level": 5, "party_size": 4})
        vault = state.room_graph.get_node("vault")
        loot = vault.metadata.get("loot", {})
        assert loot.get("gold", 0) > 0 or loot.get("items", [])

    def test_entrance_gets_nothing(self):
        state = make_state_with_encounters()
        LootAgent().execute(state, {"profile": DUNGEON_PROFILE, "party_level": 5, "party_size": 4})
        entrance = state.room_graph.get_node("entrance")
        assert entrance.metadata.get("loot", {}).get("gold", 0) == 0

    def test_secret_room_gets_exploration_bonus(self):
        state = make_state_with_encounters()
        LootAgent().execute(state, {"profile": DUNGEON_PROFILE, "party_level": 5, "party_size": 4})
        secret = state.room_graph.get_node("secret")
        loot = secret.metadata.get("loot", {})
        assert loot.get("gold", 0) > 0 or loot.get("items", [])

    def test_deterministic(self):
        state1, state2 = make_state_with_encounters(seed=42), make_state_with_encounters(seed=42)
        params = {"profile": DUNGEON_PROFILE, "party_level": 5, "party_size": 4}
        LootAgent().execute(state1, params)
        LootAgent().execute(state2, params)
        for n1, n2 in zip(state1.room_graph.nodes, state2.room_graph.nodes):
            assert n1.metadata.get("loot") == n2.metadata.get("loot")

    def test_no_graph_skips(self):
        state = SharedState(MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42))
        result = LootAgent().execute(state, {"profile": DUNGEON_PROFILE, "party_level": 3, "party_size": 4})
        assert result["status"] == "completed"

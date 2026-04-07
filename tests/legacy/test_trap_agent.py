# tests/test_trap_agent.py
"""Tests for TrapAgent — danger-map-based trap placement."""

import sys, os, numpy as np, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from agents.trap_agent import TrapAgent
from data.room_graph import RoomGraph, RoomNode, GraphEdge

def make_state_with_purposes(seed=42):
    config = MapConfig(width=256, height=256, biome="dungeon", map_type="dungeon", seed=seed)
    state = SharedState(config)
    graph = RoomGraph()
    rooms = [
        ("entrance", 0, {"entrance"}, "entrance"),
        ("guard1", 1, set(), "guard_room"),
        ("storage", 1, set(), "storage"),
        ("vault", 2, set(), "treasure_vault"),
        ("shrine", 2, set(), "shrine"),
        ("boss", 3, {"boss"}, "boss_lair"),
    ]
    for name, zone, tags, purpose in rooms:
        node = RoomNode(name, zone=zone, tags=tags, position=(20, 20), size=(30, 20))
        node.purpose = purpose
        graph.add_node(node)
    graph.add_edge(GraphEdge("entrance", "guard1", "corridor"))
    graph.add_edge(GraphEdge("guard1", "storage", "corridor"))
    graph.add_edge(GraphEdge("guard1", "vault", "corridor"))
    graph.add_edge(GraphEdge("storage", "shrine", "corridor"))
    graph.add_edge(GraphEdge("shrine", "boss", "corridor"))
    state.room_graph = graph
    return state

DUNGEON_PROFILE = {"family": "underground", "trap_density": 0.5}

class TestTrapPlacement:
    def test_some_rooms_get_traps(self):
        state = make_state_with_purposes()
        TrapAgent().execute(state, {"profile": DUNGEON_PROFILE})
        trapped = sum(1 for n in state.room_graph.nodes if n.metadata.get("trap"))
        assert trapped >= 1

    def test_safe_haven_never_trapped(self):
        state = make_state_with_purposes()
        # Change shrine to safe_haven
        state.room_graph.get_node("shrine").purpose = "safe_haven"
        TrapAgent().execute(state, {"profile": DUNGEON_PROFILE})
        safe = state.room_graph.get_node("shrine")
        assert not safe.metadata.get("trap"), "Safe haven should never have traps"

    def test_treasure_vault_high_trap_chance(self):
        """Treasure vaults have trap_chance=0.8, so with density 1.0 they should almost always get traps."""
        state = make_state_with_purposes(seed=1)
        TrapAgent().execute(state, {"profile": {"family": "underground", "trap_density": 1.0}})
        vault = state.room_graph.get_node("vault")
        assert vault.metadata.get("trap") is not None

    def test_trap_has_type_and_damage(self):
        state = make_state_with_purposes()
        TrapAgent().execute(state, {"profile": {"family": "underground", "trap_density": 1.0}})
        for node in state.room_graph.nodes:
            trap = node.metadata.get("trap")
            if trap:
                assert "type" in trap
                assert "damage" in trap
                assert trap["damage"] > 0

    def test_deterministic(self):
        state1, state2 = make_state_with_purposes(seed=42), make_state_with_purposes(seed=42)
        TrapAgent().execute(state1, {"profile": DUNGEON_PROFILE})
        TrapAgent().execute(state2, {"profile": DUNGEON_PROFILE})
        for n1, n2 in zip(state1.room_graph.nodes, state2.room_graph.nodes):
            assert n1.metadata.get("trap") == n2.metadata.get("trap")

    def test_no_graph_skips(self):
        state = SharedState(MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42))
        result = TrapAgent().execute(state, {"profile": DUNGEON_PROFILE})
        assert result["status"] == "completed"

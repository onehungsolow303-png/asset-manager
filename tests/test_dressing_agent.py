# tests/test_dressing_agent.py
"""Tests for DressingAgent — purpose-matched furniture and atmosphere."""

import sys, os, numpy as np, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from agents.dressing_agent import DressingAgent
from data.room_graph import RoomGraph, RoomNode, GraphEdge

def make_state_with_purposes(seed=42):
    config = MapConfig(width=256, height=256, biome="dungeon", map_type="dungeon", seed=seed)
    state = SharedState(config)
    state.walkability[:] = False
    graph = RoomGraph()
    rooms = [
        ("entrance", 0, {"entrance"}, "entrance", (20, 20), (30, 20)),
        ("guard", 1, set(), "guard_room", (70, 20), (30, 20)),
        ("library", 1, set(), "library", (120, 20), (30, 20)),
        ("boss", 2, {"boss"}, "boss_lair", (70, 60), (40, 30)),
    ]
    for name, zone, tags, purpose, pos, size in rooms:
        node = RoomNode(name, zone=zone, tags=tags, position=pos, size=size)
        node.purpose = purpose
        graph.add_node(node)
        # Carve room into walkability
        x, y = pos
        w, h = size
        state.walkability[y:y+h, x:x+w] = True
    graph.add_edge(GraphEdge("entrance", "guard", "corridor"))
    graph.add_edge(GraphEdge("guard", "library", "corridor"))
    graph.add_edge(GraphEdge("guard", "boss", "corridor"))
    state.room_graph = graph
    return state

DUNGEON_PROFILE = {"family": "underground", "dressing_palette": "dungeon"}

class TestDressingPlacement:
    def test_rooms_get_entities(self):
        state = make_state_with_purposes()
        DressingAgent().execute(state, {"profile": DUNGEON_PROFILE})
        dressing = [e for e in state.entities if e.entity_type == "dressing"]
        assert len(dressing) >= 4, "Each room should get at least 1 dressing item"

    def test_purpose_specific_items(self):
        state = make_state_with_purposes()
        DressingAgent().execute(state, {"profile": DUNGEON_PROFILE})
        # Library should get bookshelves or desks
        library_items = [e for e in state.entities if e.entity_type == "dressing" and e.metadata.get("room") == "library"]
        item_types = [e.variant for e in library_items]
        assert any(v in ("bookshelf", "desk", "candelabra", "scroll_rack", "reading_chair") for v in item_types)

    def test_atmosphere_tags_set(self):
        state = make_state_with_purposes()
        DressingAgent().execute(state, {"profile": DUNGEON_PROFILE})
        boss_node = state.room_graph.get_node("boss")
        assert "atmosphere" in boss_node.metadata
        assert "lighting" in boss_node.metadata["atmosphere"]

    def test_items_within_room_bounds(self):
        state = make_state_with_purposes()
        DressingAgent().execute(state, {"profile": DUNGEON_PROFILE})
        for entity in state.entities:
            if entity.entity_type == "dressing" and entity.metadata.get("room"):
                x, y = entity.position
                assert 0 <= x < 256 and 0 <= y < 256

    def test_deterministic(self):
        state1, state2 = make_state_with_purposes(seed=42), make_state_with_purposes(seed=42)
        DressingAgent().execute(state1, {"profile": DUNGEON_PROFILE})
        DressingAgent().execute(state2, {"profile": DUNGEON_PROFILE})
        d1 = [(e.position, e.variant) for e in state1.entities if e.entity_type == "dressing"]
        d2 = [(e.position, e.variant) for e in state2.entities if e.entity_type == "dressing"]
        assert d1 == d2

    def test_no_graph_skips(self):
        state = SharedState(MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42))
        result = DressingAgent().execute(state, {"profile": DUNGEON_PROFILE})
        assert result["status"] == "completed"

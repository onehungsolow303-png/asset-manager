"""Tests for StructureAgent RoomGraph-based room placement."""

import sys, os, numpy as np, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from agents.structure_agent import StructureAgent
from data.room_graph import RoomGraph, RoomNode, GraphEdge

def make_state_with_graph(room_count=5, seed=42, size=256):
    config = MapConfig(width=size, height=size, biome="dungeon", map_type="dungeon", seed=seed)
    state = SharedState(config)
    state.walkability[:] = False
    graph = RoomGraph()
    for i in range(room_count):
        tags = set()
        if i == 0: tags.add("entrance")
        if i == room_count - 1: tags.add("boss")
        graph.add_node(RoomNode(f"room_{i}", zone=i, tags=tags))
    for i in range(room_count - 1):
        graph.add_edge(GraphEdge(f"room_{i}", f"room_{i+1}", "corridor"))
    state.room_graph = graph
    return state

class TestRoomGraphPlacement:
    def test_places_all_rooms(self):
        state = make_state_with_graph(room_count=5)
        StructureAgent().execute(state, {"type": "dungeon", "use_room_graph": True})
        for node in state.room_graph.nodes:
            assert node.position is not None, f"{node.node_id} has no position"
            assert node.size is not None, f"{node.node_id} has no size"

    def test_rooms_dont_overlap(self):
        state = make_state_with_graph(room_count=5, size=512)
        StructureAgent().execute(state, {"type": "dungeon", "use_room_graph": True})
        nodes = state.room_graph.nodes
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a, b = nodes[i], nodes[j]
                ax, ay = a.position
                aw, ah = a.size
                bx, by = b.position
                bw, bh = b.size
                overlap = (ax < bx + bw + 4 and ax + aw + 4 > bx and ay < by + bh + 4 and ay + ah + 4 > by)
                assert not overlap, f"{a.node_id} overlaps {b.node_id}"

    def test_rooms_carved_into_walkability(self):
        state = make_state_with_graph(room_count=3)
        StructureAgent().execute(state, {"type": "dungeon", "use_room_graph": True})
        assert state.walkability.sum() > 0

    def test_creates_entities(self):
        state = make_state_with_graph(room_count=3)
        StructureAgent().execute(state, {"type": "dungeon", "use_room_graph": True})
        room_entities = [e for e in state.entities if e.entity_type == "room"]
        assert len(room_entities) >= 3

    def test_uses_cave_openings_when_available(self):
        state = make_state_with_graph(room_count=3, size=256)
        state.cave_mask = np.zeros((256, 256), dtype=bool)
        state.cave_mask[50:150, 50:150] = True
        state.natural_openings = [(50, 50, 100, 100)]
        StructureAgent().execute(state, {"type": "dungeon", "use_room_graph": True})
        rooms_in_cave = sum(1 for n in state.room_graph.nodes if 50 <= n.position[0] <= 150 and 50 <= n.position[1] <= 150)
        assert rooms_in_cave >= 1

    def test_deterministic(self):
        state1, state2 = make_state_with_graph(seed=42), make_state_with_graph(seed=42)
        params = {"type": "dungeon", "use_room_graph": True}
        StructureAgent().execute(state1, params)
        StructureAgent().execute(state2, params)
        for n1, n2 in zip(state1.room_graph.nodes, state2.room_graph.nodes):
            assert n1.position == n2.position
            assert n1.size == n2.size

    def test_existing_generators_still_work(self):
        """Existing dungeon generation without room graph should still work."""
        config = MapConfig(width=256, height=256, biome="dungeon", map_type="dungeon", seed=42)
        state = SharedState(config)
        state.walkability[:] = False
        state.terrain_color[:] = (40, 38, 35)
        result = StructureAgent().execute(state, {"type": "dungeon", "building_count": 5})
        assert result["status"] == "completed"

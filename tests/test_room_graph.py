"""Tests for RoomGraph, RoomNode, GraphEdge data structures."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from data.room_graph import RoomNode, GraphEdge, RoomGraph


class TestRoomNode:
    def test_creation(self):
        node = RoomNode(node_id="room_0", zone=0)
        assert node.node_id == "room_0"
        assert node.zone == 0
        assert node.tags == set()
        assert node.purpose is None
        assert node.position is None
        assert node.size is None
        assert node.metadata == {}

    def test_tags(self):
        node = RoomNode(node_id="entrance", zone=0, tags={"entrance", "required"})
        assert "entrance" in node.tags
        assert "required" in node.tags


class TestGraphEdge:
    def test_creation(self):
        edge = GraphEdge(from_id="room_0", to_id="room_1", connection_type="corridor")
        assert edge.from_id == "room_0"
        assert edge.to_id == "room_1"
        assert edge.connection_type == "corridor"
        assert edge.bidirectional is True

    def test_one_way(self):
        edge = GraphEdge(from_id="a", to_id="b", connection_type="one_way", bidirectional=False)
        assert edge.bidirectional is False


class TestRoomGraph:
    def test_empty_graph(self):
        g = RoomGraph()
        assert g.node_count == 0
        assert g.edge_count == 0

    def test_add_node(self):
        g = RoomGraph()
        g.add_node(RoomNode("room_0", zone=0))
        assert g.node_count == 1
        assert g.get_node("room_0").zone == 0

    def test_add_edge(self):
        g = RoomGraph()
        g.add_node(RoomNode("a", zone=0))
        g.add_node(RoomNode("b", zone=1))
        g.add_edge(GraphEdge("a", "b", "corridor"))
        assert g.edge_count == 1
        assert g.neighbors("a") == ["b"]
        assert g.neighbors("b") == ["a"]

    def test_one_way_edge(self):
        g = RoomGraph()
        g.add_node(RoomNode("a", zone=0))
        g.add_node(RoomNode("b", zone=1))
        g.add_edge(GraphEdge("a", "b", "one_way", bidirectional=False))
        assert g.neighbors("a") == ["b"]
        assert g.neighbors("b") == []

    def test_add_edge_unknown_node_raises(self):
        g = RoomGraph()
        g.add_node(RoomNode("a", zone=0))
        with pytest.raises(ValueError, match="Unknown node"):
            g.add_edge(GraphEdge("a", "missing", "corridor"))

    def test_get_nodes_by_zone(self):
        g = RoomGraph()
        g.add_node(RoomNode("a", zone=0))
        g.add_node(RoomNode("b", zone=0))
        g.add_node(RoomNode("c", zone=1))
        assert len(g.get_nodes_by_zone(0)) == 2
        assert len(g.get_nodes_by_zone(1)) == 1

    def test_entrance_and_boss_nodes(self):
        g = RoomGraph()
        g.add_node(RoomNode("entrance", zone=0, tags={"entrance"}))
        g.add_node(RoomNode("boss", zone=3, tags={"boss"}))
        assert g.entrance_node.node_id == "entrance"
        assert g.boss_node.node_id == "boss"

    def test_graph_distance(self):
        g = RoomGraph()
        g.add_node(RoomNode("a", zone=0))
        g.add_node(RoomNode("b", zone=1))
        g.add_node(RoomNode("c", zone=2))
        g.add_edge(GraphEdge("a", "b", "corridor"))
        g.add_edge(GraphEdge("b", "c", "corridor"))
        assert g.distance("a", "c") == 2
        assert g.distance("a", "a") == 0

    def test_max_zone(self):
        g = RoomGraph()
        g.add_node(RoomNode("a", zone=0))
        g.add_node(RoomNode("b", zone=3))
        assert g.max_zone == 3

    def test_all_reachable_from(self):
        g = RoomGraph()
        g.add_node(RoomNode("a", zone=0))
        g.add_node(RoomNode("b", zone=1))
        g.add_node(RoomNode("c", zone=2))
        g.add_edge(GraphEdge("a", "b", "corridor"))
        g.add_edge(GraphEdge("b", "c", "corridor"))
        assert g.all_reachable_from("a") is True

    def test_unreachable_detected(self):
        g = RoomGraph()
        g.add_node(RoomNode("a", zone=0))
        g.add_node(RoomNode("b", zone=1))
        g.add_node(RoomNode("orphan", zone=0))
        g.add_edge(GraphEdge("a", "b", "corridor"))
        assert g.all_reachable_from("a") is False

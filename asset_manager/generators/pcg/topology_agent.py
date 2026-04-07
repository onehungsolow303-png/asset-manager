"""
TopologyAgent — Generates an abstract RoomGraph (nodes = room slots, edges = connections)
before any spatial placement. Supports 4 topology types: linear_with_branches, loop_based,
hub_and_spoke, and hybrid.
"""

import numpy as np
from collections import deque
from .base_agent import BaseAgent
from asset_manager.shared_state import SharedState
from .data.room_graph import RoomGraph, RoomNode, GraphEdge
from typing import Any


class TopologyAgent(BaseAgent):
    name = "TopologyAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        topology_preference: list[str] = params.get("topology_preference", ["linear_with_branches"])
        size_topology_override: dict[str, str] = params.get("size_topology_override", {})
        size: str = params.get("size", "standard")
        room_count: int = params.get("room_count", 10)

        # Select topology type
        if size in size_topology_override:
            topology = size_topology_override[size]
        else:
            topology = topology_preference[0] if topology_preference else "linear_with_branches"

        rng = np.random.default_rng(shared_state.config.seed + 800)

        if topology == "linear_with_branches":
            graph = self._build_linear(room_count, rng)
        elif topology == "loop_based":
            graph = self._build_loop(room_count, rng)
        elif topology == "hub_and_spoke":
            graph = self._build_hub_and_spoke(room_count, rng)
        elif topology == "hybrid":
            graph = self._build_hybrid(room_count, rng)
        else:
            # Default fallback
            graph = self._build_linear(room_count, rng)

        self._assign_zones(graph, room_count)
        shared_state.room_graph = graph

        return {
            "topology": topology,
            "node_count": graph.node_count,
            "edge_count": graph.edge_count,
            "max_zone": graph.max_zone,
            "entrance_node": graph.entrance_node.node_id if graph.entrance_node else None,
            "boss_node": graph.boss_node.node_id if graph.boss_node else None,
        }

    # ------------------------------------------------------------------
    # Topology builders
    # ------------------------------------------------------------------

    def _build_linear(self, room_count: int, rng: np.random.Generator) -> RoomGraph:
        """Main chain with branch rooms hanging off random chain nodes."""
        graph = RoomGraph()
        main_count = max(3, room_count * 2 // 3)
        branch_count = room_count - main_count

        # Create main chain nodes
        main_ids = [f"room_{i}" for i in range(main_count)]
        for nid in main_ids:
            graph.add_node(RoomNode(node_id=nid, zone=0))

        # Connect main chain sequentially
        for i in range(len(main_ids) - 1):
            graph.add_edge(GraphEdge(
                from_id=main_ids[i],
                to_id=main_ids[i + 1],
                connection_type="corridor",
                bidirectional=True,
            ))

        # Create branch nodes, attach to random main-chain nodes
        branch_ids = [f"branch_{i}" for i in range(branch_count)]
        for bid in branch_ids:
            graph.add_node(RoomNode(node_id=bid, zone=0))
            attach_to = main_ids[int(rng.integers(0, len(main_ids)))]
            graph.add_edge(GraphEdge(
                from_id=attach_to,
                to_id=bid,
                connection_type="corridor",
                bidirectional=True,
            ))

        # Tag entrance (first main chain node)
        graph.get_node(main_ids[0]).tags.add("entrance")

        return graph

    def _build_loop(self, room_count: int, rng: np.random.Generator) -> RoomGraph:
        """Spanning tree with back-edges to create cycles."""
        graph = RoomGraph()
        node_ids = [f"room_{i}" for i in range(room_count)]

        for nid in node_ids:
            graph.add_node(RoomNode(node_id=nid, zone=0))

        # Build spanning tree: shuffle order for random structure, then connect sequentially
        shuffled = list(node_ids)
        rng.shuffle(shuffled)

        for i in range(len(shuffled) - 1):
            graph.add_edge(GraphEdge(
                from_id=shuffled[i],
                to_id=shuffled[i + 1],
                connection_type="corridor",
                bidirectional=True,
            ))

        # Add back-edges to create cycles
        num_back_edges = max(1, room_count // 5)
        edge_set = set()
        for edge in graph.edges:
            a, b = edge.from_id, edge.to_id
            edge_set.add((min(a, b), max(a, b)))

        attempts = 0
        added = 0
        while added < num_back_edges and attempts < room_count * 10:
            attempts += 1
            i = int(rng.integers(0, room_count))
            j = int(rng.integers(0, room_count))
            if i == j:
                continue
            a, b = node_ids[i], node_ids[j]
            key = (min(a, b), max(a, b))
            if key in edge_set:
                continue
            # Ensure not directly adjacent (back-edge only)
            if b in graph.neighbors(a):
                continue
            graph.add_edge(GraphEdge(
                from_id=a,
                to_id=b,
                connection_type="corridor",
                bidirectional=True,
            ))
            edge_set.add(key)
            added += 1

        # Tag entrance as the first node in original (non-shuffled) order
        graph.get_node(node_ids[0]).tags.add("entrance")

        return graph

    def _build_hub_and_spoke(self, room_count: int, rng: np.random.Generator) -> RoomGraph:
        """Central hub with N wings radiating out."""
        graph = RoomGraph()

        hub = RoomNode(node_id="hub", zone=0)
        graph.add_node(hub)

        # Create entrance node that connects to hub
        entrance = RoomNode(node_id="entrance", zone=0, tags={"entrance"})
        graph.add_node(entrance)
        graph.add_edge(GraphEdge(
            from_id="entrance",
            to_id="hub",
            connection_type="corridor",
            bidirectional=True,
        ))

        remaining = room_count - 2  # hub + entrance
        remaining = max(0, remaining)
        num_wings = max(1, min(remaining // 2 + 1, 5)) if remaining > 0 else 1

        # Distribute rooms across wings (round-robin)
        wings: list[list[str]] = [[] for _ in range(num_wings)]
        for i in range(remaining):
            wing_id = f"wing{i % num_wings}_room{i // num_wings}"
            wings[i % num_wings].append(wing_id)

        for wing_nodes in wings:
            for nid in wing_nodes:
                graph.add_node(RoomNode(node_id=nid, zone=0))
            if not wing_nodes:
                continue
            # First node in wing connects to hub
            graph.add_edge(GraphEdge(
                from_id="hub",
                to_id=wing_nodes[0],
                connection_type="corridor",
                bidirectional=True,
            ))
            # Subsequent nodes chain within wing
            for i in range(len(wing_nodes) - 1):
                graph.add_edge(GraphEdge(
                    from_id=wing_nodes[i],
                    to_id=wing_nodes[i + 1],
                    connection_type="corridor",
                    bidirectional=True,
                ))

        return graph

    def _build_hybrid(self, room_count: int, rng: np.random.Generator) -> RoomGraph:
        """Hub-and-spoke with loop back-edges within wings >= 3 nodes."""
        graph = self._build_hub_and_spoke(room_count, rng)

        # Collect wings by traversing hub's neighbors (excluding entrance)
        hub_neighbors = graph.neighbors("hub")

        for wing_start in hub_neighbors:
            # Walk the wing chain from wing_start
            wing_chain = [wing_start]
            visited_in_wing = {"hub", "entrance", wing_start}
            current = wing_start
            while True:
                nexts = [n for n in graph.neighbors(current) if n not in visited_in_wing]
                if not nexts:
                    break
                nxt = nexts[0]
                wing_chain.append(nxt)
                visited_in_wing.add(nxt)
                current = nxt

            if len(wing_chain) >= 3:
                # Add a back-edge between two non-adjacent nodes in the wing
                i = int(rng.integers(0, len(wing_chain) - 2))
                j = int(rng.integers(i + 2, len(wing_chain)))
                a, b = wing_chain[i], wing_chain[j]
                # Check edge doesn't already exist
                if b not in graph.neighbors(a):
                    graph.add_edge(GraphEdge(
                        from_id=a,
                        to_id=b,
                        connection_type="corridor",
                        bidirectional=True,
                    ))

        return graph

    # ------------------------------------------------------------------
    # Zone assignment
    # ------------------------------------------------------------------

    def _assign_zones(self, graph: RoomGraph, room_count: int) -> None:
        """BFS from entrance to assign zone numbers. Tags boss node as deepest zone."""
        entrance = graph.entrance_node
        if entrance is None:
            return

        zones_per_room = max(1, room_count // max(2, room_count // 3))

        # BFS to determine distances from entrance
        distances: dict[str, int] = {}
        queue: deque[str] = deque([entrance.node_id])
        distances[entrance.node_id] = 0

        while queue:
            current_id = queue.popleft()
            for neighbor_id in graph.neighbors(current_id):
                if neighbor_id not in distances:
                    distances[neighbor_id] = distances[current_id] + 1
                    queue.append(neighbor_id)

        # Assign zone to every node; handle unreachable nodes gracefully
        max_dist = max(distances.values()) if distances else 0

        for node in graph.nodes:
            dist = distances.get(node.node_id, max_dist)
            node.zone = dist // zones_per_room

        # Ensure entrance is zone 0
        entrance.zone = 0

        # Tag boss: node with the highest zone (deepest BFS distance)
        max_zone_val = max(n.zone for n in graph.nodes)
        boss_candidates = [n for n in graph.nodes if n.zone == max_zone_val and "entrance" not in n.tags]
        if boss_candidates:
            # Pick deterministically (by node_id sort) to stay reproducible
            boss_node = sorted(boss_candidates, key=lambda n: n.node_id)[-1]
            boss_node.tags.add("boss")
            # Guarantee boss has the max zone
            boss_node.zone = max_zone_val

"""RoomGraph — abstract room connectivity graph used by TopologyAgent and StructureAgent."""

from dataclasses import dataclass, field
from collections import deque


@dataclass
class RoomNode:
    """A room slot in the abstract topology graph."""
    node_id: str
    zone: int
    tags: set[str] = field(default_factory=set)
    purpose: str | None = None
    position: tuple[int, int] | None = None
    size: tuple[int, int] | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    """A connection between two room nodes."""
    from_id: str
    to_id: str
    connection_type: str
    bidirectional: bool = True
    metadata: dict = field(default_factory=dict)


class RoomGraph:
    """Directed/undirected graph of room nodes and connection edges."""

    def __init__(self):
        self._nodes: dict[str, RoomNode] = {}
        self._edges: list[GraphEdge] = []
        self._adj: dict[str, list[str]] = {}

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    @property
    def nodes(self) -> list[RoomNode]:
        return list(self._nodes.values())

    @property
    def edges(self) -> list[GraphEdge]:
        return list(self._edges)

    @property
    def max_zone(self) -> int:
        if not self._nodes:
            return 0
        return max(n.zone for n in self._nodes.values())

    @property
    def entrance_node(self) -> RoomNode | None:
        for n in self._nodes.values():
            if "entrance" in n.tags:
                return n
        return None

    @property
    def boss_node(self) -> RoomNode | None:
        for n in self._nodes.values():
            if "boss" in n.tags:
                return n
        return None

    def add_node(self, node: RoomNode) -> None:
        self._nodes[node.node_id] = node
        if node.node_id not in self._adj:
            self._adj[node.node_id] = []

    def get_node(self, node_id: str) -> RoomNode:
        return self._nodes[node_id]

    def add_edge(self, edge: GraphEdge) -> None:
        if edge.from_id not in self._nodes:
            raise ValueError(f"Unknown node: {edge.from_id}")
        if edge.to_id not in self._nodes:
            raise ValueError(f"Unknown node: {edge.to_id}")
        self._edges.append(edge)
        self._adj[edge.from_id].append(edge.to_id)
        if edge.bidirectional:
            self._adj[edge.to_id].append(edge.from_id)

    def neighbors(self, node_id: str) -> list[str]:
        return list(self._adj.get(node_id, []))

    def get_nodes_by_zone(self, zone: int) -> list[RoomNode]:
        return [n for n in self._nodes.values() if n.zone == zone]

    def distance(self, from_id: str, to_id: str) -> int:
        if from_id == to_id:
            return 0
        visited = {from_id}
        queue = deque([(from_id, 0)])
        while queue:
            current, dist = queue.popleft()
            for neighbor in self._adj.get(current, []):
                if neighbor == to_id:
                    return dist + 1
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))
        return -1

    def all_reachable_from(self, start_id: str) -> bool:
        undirected: dict[str, set[str]] = {nid: set() for nid in self._nodes}
        for edge in self._edges:
            undirected[edge.from_id].add(edge.to_id)
            undirected[edge.to_id].add(edge.from_id)
        visited = set()
        queue = deque([start_id])
        visited.add(start_id)
        while queue:
            current = queue.popleft()
            for neighbor in undirected[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return len(visited) == len(self._nodes)

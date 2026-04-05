# Generation Overhaul Phase 1: Foundation + Terrain

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the data foundation (profiles, room graph, generation request), pipeline coordinator skeleton, and Phase 1 terrain agents (CaveCarverAgent + TerrainAgent enhancements) so that terrain generation + cave carving runs through the new pipeline and produces validated output.

**Architecture:** New `pipeline/` package holds coordinator, profiles, validation. New `data/` package holds room graph, room purposes, and game tables. CaveCarverAgent is a new agent in `agents/`. TerrainAgent gets enhanced to expose raw noise layers for CaveCarver consumption. PipelineCoordinator runs Phase 1 only in this plan — Phases 2-3 are stubs that pass through to existing agents.

**Tech Stack:** Python 3.11+, numpy, pytest

**Spec:** `docs/superpowers/specs/2026-04-04-generation-overhaul-design.md`

**Plan series:**
- **Phase 1 (this plan):** Foundation + Terrain
- Phase 2: Layout agents (TopologyAgent, ConnectorAgent, StructureAgent/PathfindingAgent enhancements)
- Phase 3: Population agents (RoomPurposeAgent, EncounterAgent, TrapAgent, LootAgent, DressingAgent, SpawnAgent enhancements)
- Phase 4: Integration + end-to-end validation

---

## File Map

### New Files

| File | Responsibility |
|------|---------------|
| `mapgen_agents/pipeline/__init__.py` | Package init — exports PipelineCoordinator, GenerationRequest |
| `mapgen_agents/pipeline/generation_request.py` | GenerationRequest dataclass |
| `mapgen_agents/pipeline/profiles.py` | FAMILIES, MAP_TYPE_PROFILES (all 34), profile lookup |
| `mapgen_agents/pipeline/coordinator.py` | PipelineCoordinator — 3-phase orchestration, validation gates, retry |
| `mapgen_agents/pipeline/validation.py` | validate_terrain(), validate_layout(), validate_population() |
| `mapgen_agents/data/__init__.py` | Package init |
| `mapgen_agents/data/room_graph.py` | RoomNode, GraphEdge, RoomGraph dataclasses |
| `mapgen_agents/data/room_purposes.py` | ROOM_PURPOSES dict, ADJACENCY_RULES dict |
| `mapgen_agents/data/game_tables.py` | PARTY_XP_TABLE, TREASURE_TABLE, SIZE_ROOM_COUNTS |
| `mapgen_agents/agents/cave_carver_agent.py` | CaveCarverAgent — noise-threshold carving + cellular automata |
| `tests/test_generation_request.py` | Tests for GenerationRequest |
| `tests/test_profiles.py` | Tests for profile registry |
| `tests/test_room_graph.py` | Tests for RoomGraph data structures |
| `tests/test_room_purposes.py` | Tests for room purpose definitions |
| `tests/test_game_tables.py` | Tests for XP/treasure/room count tables |
| `tests/test_cave_carver.py` | Tests for CaveCarverAgent |
| `tests/test_validation.py` | Tests for phase validation functions |
| `tests/test_pipeline_coordinator.py` | Tests for PipelineCoordinator |

### Modified Files

| File | Changes |
|------|---------|
| `mapgen_agents/agents/terrain_agent.py` | Add `flat_floor` and `road_ready` presets. Store raw noise in `shared_state.metadata["raw_elevation"]` for CaveCarver. |
| `mapgen_agents/shared_state.py` | Add `cave_mask`, `natural_openings`, and `room_graph` fields to SharedState. |

---

## Task 1: GenerationRequest Dataclass

**Files:**
- Create: `mapgen_agents/pipeline/__init__.py`
- Create: `mapgen_agents/pipeline/generation_request.py`
- Test: `tests/test_generation_request.py`

- [ ] **Step 1: Create pipeline package and write failing test**

```python
# tests/test_generation_request.py
"""Tests for GenerationRequest dataclass."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from pipeline.generation_request import GenerationRequest


class TestGenerationRequest:
    def test_creation_with_all_fields(self):
        req = GenerationRequest(
            map_type="dungeon",
            biome="dungeon",
            size="standard",
            seed=42,
            party_level=5,
            party_size=4,
            output_dir="./output",
            unity_export=True,
        )
        assert req.map_type == "dungeon"
        assert req.biome == "dungeon"
        assert req.size == "standard"
        assert req.seed == 42
        assert req.party_level == 5
        assert req.party_size == 4
        assert req.output_dir == "./output"
        assert req.unity_export is True

    def test_defaults(self):
        req = GenerationRequest(map_type="village", biome="forest", size="standard", seed=1)
        assert req.party_level == 3
        assert req.party_size == 4
        assert req.output_dir == "./output"
        assert req.unity_export is False

    def test_party_level_bounds(self):
        with pytest.raises(ValueError, match="party_level"):
            GenerationRequest(map_type="dungeon", biome="dungeon", size="standard", seed=1, party_level=0)
        with pytest.raises(ValueError, match="party_level"):
            GenerationRequest(map_type="dungeon", biome="dungeon", size="standard", seed=1, party_level=21)

    def test_valid_size_presets(self):
        for size in ["small_encounter", "medium_encounter", "large_encounter", "standard", "large", "region", "open_world"]:
            req = GenerationRequest(map_type="dungeon", biome="dungeon", size=size, seed=1)
            assert req.size == size

    def test_invalid_size(self):
        with pytest.raises(ValueError, match="size"):
            GenerationRequest(map_type="dungeon", biome="dungeon", size="tiny", seed=1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_generation_request.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline'`

- [ ] **Step 3: Implement GenerationRequest**

```python
# mapgen_agents/pipeline/__init__.py
from pipeline.generation_request import GenerationRequest

__all__ = ["GenerationRequest"]
```

```python
# mapgen_agents/pipeline/generation_request.py
"""GenerationRequest — input to the PipelineCoordinator."""

from dataclasses import dataclass

VALID_SIZES = [
    "small_encounter", "medium_encounter", "large_encounter",
    "standard", "large", "region", "open_world",
]


@dataclass
class GenerationRequest:
    """Everything the PipelineCoordinator needs to generate a map."""
    map_type: str
    biome: str
    size: str
    seed: int
    party_level: int = 3
    party_size: int = 4
    output_dir: str = "./output"
    unity_export: bool = False

    def __post_init__(self):
        if self.party_level < 1 or self.party_level > 20:
            raise ValueError(f"party_level must be 1-20, got {self.party_level}")
        if self.party_size < 1:
            raise ValueError(f"party_size must be >= 1, got {self.party_size}")
        if self.size not in VALID_SIZES:
            raise ValueError(f"size must be one of {VALID_SIZES}, got '{self.size}'")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_generation_request.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
cd "C:/Dev/Map Generator"
git add mapgen_agents/pipeline/__init__.py mapgen_agents/pipeline/generation_request.py tests/test_generation_request.py
git commit -m "feat: add GenerationRequest dataclass for pipeline input"
```

---

## Task 2: RoomGraph Data Structures

**Files:**
- Create: `mapgen_agents/data/__init__.py`
- Create: `mapgen_agents/data/room_graph.py`
- Test: `tests/test_room_graph.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_room_graph.py
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
        assert g.neighbors("b") == ["a"]  # bidirectional

    def test_one_way_edge(self):
        g = RoomGraph()
        g.add_node(RoomNode("a", zone=0))
        g.add_node(RoomNode("b", zone=1))
        g.add_edge(GraphEdge("a", "b", "one_way", bidirectional=False))
        assert g.neighbors("a") == ["b"]
        assert g.neighbors("b") == []  # one-way

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_room_graph.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'data'`

- [ ] **Step 3: Implement RoomGraph**

```python
# mapgen_agents/data/__init__.py
from data.room_graph import RoomNode, GraphEdge, RoomGraph

__all__ = ["RoomNode", "GraphEdge", "RoomGraph"]
```

```python
# mapgen_agents/data/room_graph.py
"""RoomGraph — abstract room connectivity graph used by TopologyAgent and StructureAgent."""

from dataclasses import dataclass, field
from collections import deque


@dataclass
class RoomNode:
    """A room slot in the abstract topology graph."""
    node_id: str
    zone: int                               # difficulty zone (0=outer, N=boss)
    tags: set[str] = field(default_factory=set)  # "entrance", "boss", "treasure", "secret"
    purpose: str | None = None              # assigned by RoomPurposeAgent (None until Phase 3)
    position: tuple[int, int] | None = None # (x, y) assigned by StructureAgent (None until Phase 2)
    size: tuple[int, int] | None = None     # (w, h) assigned by StructureAgent (None until Phase 2)
    metadata: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    """A connection between two room nodes."""
    from_id: str
    to_id: str
    connection_type: str   # "corridor", "door", "locked_door", "secret", "one_way", "stairs"
    bidirectional: bool = True
    metadata: dict = field(default_factory=dict)


class RoomGraph:
    """Directed/undirected graph of room nodes and connection edges."""

    def __init__(self):
        self._nodes: dict[str, RoomNode] = {}
        self._edges: list[GraphEdge] = []
        self._adj: dict[str, list[str]] = {}  # adjacency list (respects directionality)

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
        """BFS shortest path distance. Returns -1 if unreachable."""
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
        """Check if all nodes are reachable from start via BFS (ignoring edge direction)."""
        # Build undirected adjacency for reachability check
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_room_graph.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
cd "C:/Dev/Map Generator"
git add mapgen_agents/data/__init__.py mapgen_agents/data/room_graph.py tests/test_room_graph.py
git commit -m "feat: add RoomGraph data structures for topology engine"
```

---

## Task 3: Room Purpose Definitions

**Files:**
- Create: `mapgen_agents/data/room_purposes.py`
- Test: `tests/test_room_purposes.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_room_purposes.py
"""Tests for room purpose definitions and adjacency rules."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from data.room_purposes import ROOM_PURPOSES, ADJACENCY_RULES


class TestRoomPurposes:
    def test_all_purposes_have_required_keys(self):
        required = {"encounter_mult", "trap_chance", "loot_mult"}
        for name, purpose in ROOM_PURPOSES.items():
            assert required.issubset(purpose.keys()), f"{name} missing keys: {required - purpose.keys()}"

    def test_encounter_mult_non_negative(self):
        for name, purpose in ROOM_PURPOSES.items():
            assert purpose["encounter_mult"] >= 0.0, f"{name} has negative encounter_mult"

    def test_trap_chance_in_range(self):
        for name, purpose in ROOM_PURPOSES.items():
            assert 0.0 <= purpose["trap_chance"] <= 1.0, f"{name} trap_chance out of range"

    def test_loot_mult_non_negative(self):
        for name, purpose in ROOM_PURPOSES.items():
            assert purpose["loot_mult"] >= 0.0, f"{name} has negative loot_mult"

    def test_boss_lair_is_strongest(self):
        assert ROOM_PURPOSES["boss_lair"]["encounter_mult"] >= 2.0
        assert ROOM_PURPOSES["boss_lair"]["loot_mult"] >= 2.0

    def test_safe_haven_has_no_danger(self):
        assert ROOM_PURPOSES["safe_haven"]["encounter_mult"] == 0.0
        assert ROOM_PURPOSES["safe_haven"]["trap_chance"] == 0.0

    def test_minimum_purpose_count(self):
        assert len(ROOM_PURPOSES) >= 16


class TestAdjacencyRules:
    def test_underground_family_exists(self):
        assert "underground" in ADJACENCY_RULES

    def test_adjacency_has_near_and_far(self):
        for family, rules in ADJACENCY_RULES.items():
            for purpose, adj in rules.items():
                assert "near" in adj, f"{family}.{purpose} missing 'near'"
                assert "far" in adj, f"{family}.{purpose} missing 'far'"

    def test_guard_room_near_entrance(self):
        assert "entrance" in ADJACENCY_RULES["underground"]["guard_room"]["near"]

    def test_boss_lair_far_from_entrance(self):
        assert "entrance" in ADJACENCY_RULES["underground"]["boss_lair"]["far"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_room_purposes.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement room purposes**

```python
# mapgen_agents/data/room_purposes.py
"""Room purpose definitions and adjacency rules for the generation pipeline."""

# Each purpose has gameplay multipliers used by EncounterAgent, TrapAgent, LootAgent.
# encounter_mult: multiplier on XP budget for this room
# trap_chance: probability of trap placement (before profile.trap_density roll)
# loot_mult: multiplier on loot allocation for this room
ROOM_PURPOSES: dict[str, dict] = {
    # Combat rooms
    "guard_room":     {"encounter_mult": 1.2, "trap_chance": 0.2, "loot_mult": 0.5},
    "barracks":       {"encounter_mult": 1.5, "trap_chance": 0.1, "loot_mult": 0.3},
    "arena":          {"encounter_mult": 2.0, "trap_chance": 0.0, "loot_mult": 0.8},
    "boss_lair":      {"encounter_mult": 3.0, "trap_chance": 0.3, "loot_mult": 2.5},

    # Treasure rooms
    "treasure_vault": {"encounter_mult": 0.5, "trap_chance": 0.8, "loot_mult": 3.0},
    "armory":         {"encounter_mult": 0.3, "trap_chance": 0.4, "loot_mult": 2.0},

    # Utility rooms
    "storage":        {"encounter_mult": 0.2, "trap_chance": 0.1, "loot_mult": 0.4},
    "alchemy_lab":    {"encounter_mult": 0.3, "trap_chance": 0.5, "loot_mult": 1.5},
    "library":        {"encounter_mult": 0.1, "trap_chance": 0.3, "loot_mult": 1.2},

    # Atmospheric rooms
    "shrine":         {"encounter_mult": 0.0, "trap_chance": 0.2, "loot_mult": 0.8},
    "crypt":          {"encounter_mult": 0.8, "trap_chance": 0.4, "loot_mult": 1.0},
    "cell":           {"encounter_mult": 0.3, "trap_chance": 0.1, "loot_mult": 0.1},
    "safe_haven":     {"encounter_mult": 0.0, "trap_chance": 0.0, "loot_mult": 0.2},

    # Structural rooms
    "entrance":       {"encounter_mult": 0.3, "trap_chance": 0.1, "loot_mult": 0.0},
    "corridor_hub":   {"encounter_mult": 0.5, "trap_chance": 0.3, "loot_mult": 0.1},
    "secret_chamber": {"encounter_mult": 0.0, "trap_chance": 0.6, "loot_mult": 2.0},
    "portal_room":    {"encounter_mult": 0.5, "trap_chance": 0.3, "loot_mult": 0.5},

    # Settlement-specific
    "town_square":    {"encounter_mult": 0.0, "trap_chance": 0.0, "loot_mult": 0.0},
    "house":          {"encounter_mult": 0.1, "trap_chance": 0.0, "loot_mult": 0.2},
    "tavern":         {"encounter_mult": 0.2, "trap_chance": 0.0, "loot_mult": 0.3},
    "shop":           {"encounter_mult": 0.1, "trap_chance": 0.1, "loot_mult": 0.8},
    "farm":           {"encounter_mult": 0.1, "trap_chance": 0.0, "loot_mult": 0.1},
    "well":           {"encounter_mult": 0.0, "trap_chance": 0.0, "loot_mult": 0.0},
    "blacksmith":     {"encounter_mult": 0.1, "trap_chance": 0.0, "loot_mult": 1.0},
    "inn":            {"encounter_mult": 0.1, "trap_chance": 0.0, "loot_mult": 0.3},
    "stable":         {"encounter_mult": 0.1, "trap_chance": 0.0, "loot_mult": 0.1},
    "manor":          {"encounter_mult": 0.3, "trap_chance": 0.2, "loot_mult": 1.5},
    "hidden_cellar":  {"encounter_mult": 0.5, "trap_chance": 0.5, "loot_mult": 2.0},

    # Interior-specific
    "common_room":    {"encounter_mult": 0.2, "trap_chance": 0.0, "loot_mult": 0.2},
    "kitchen":        {"encounter_mult": 0.1, "trap_chance": 0.0, "loot_mult": 0.1},
    "bar":            {"encounter_mult": 0.2, "trap_chance": 0.0, "loot_mult": 0.3},
    "guest_room":     {"encounter_mult": 0.1, "trap_chance": 0.0, "loot_mult": 0.3},
    "cellar":         {"encounter_mult": 0.3, "trap_chance": 0.3, "loot_mult": 0.5},
    "owner_quarters": {"encounter_mult": 0.2, "trap_chance": 0.2, "loot_mult": 0.8},
    "gambling_den":   {"encounter_mult": 0.4, "trap_chance": 0.2, "loot_mult": 1.0},
}


# Soft adjacency constraints per family. "near" = preferred neighbors, "far" = avoid.
ADJACENCY_RULES: dict[str, dict[str, dict]] = {
    "underground": {
        "guard_room":     {"near": ["entrance", "treasure_vault", "boss_lair"], "far": ["safe_haven"]},
        "barracks":       {"near": ["armory", "guard_room", "storage"],         "far": ["boss_lair"]},
        "treasure_vault": {"near": ["guard_room"],                              "far": ["entrance"]},
        "boss_lair":      {"near": ["treasure_vault"],                          "far": ["entrance", "safe_haven"]},
        "safe_haven":     {"near": ["entrance"],                                "far": ["boss_lair", "guard_room"]},
        "alchemy_lab":    {"near": ["library", "storage"],                      "far": []},
        "library":        {"near": ["alchemy_lab", "shrine"],                   "far": []},
        "shrine":         {"near": ["crypt", "library"],                        "far": ["barracks"]},
        "armory":         {"near": ["barracks", "guard_room"],                  "far": []},
        "storage":        {"near": ["barracks", "kitchen"],                     "far": []},
        "cell":           {"near": ["guard_room"],                              "far": ["treasure_vault"]},
        "entrance":       {"near": ["guard_room", "safe_haven"],                "far": ["boss_lair"]},
    },
    "fortification": {
        "guard_room":     {"near": ["entrance", "armory"],                      "far": []},
        "barracks":       {"near": ["armory", "storage"],                       "far": []},
        "armory":         {"near": ["barracks", "guard_room"],                  "far": []},
        "boss_lair":      {"near": ["treasure_vault"],                          "far": ["entrance"]},
        "treasure_vault": {"near": ["guard_room", "boss_lair"],                 "far": ["entrance"]},
        "entrance":       {"near": ["guard_room"],                              "far": ["boss_lair"]},
    },
    "settlement": {
        "tavern":         {"near": ["town_square", "inn"],                      "far": []},
        "shop":           {"near": ["town_square", "blacksmith"],               "far": []},
        "blacksmith":     {"near": ["shop", "stable"],                          "far": []},
        "house":          {"near": ["well", "farm"],                            "far": []},
        "town_square":    {"near": ["tavern", "shop", "entrance"],              "far": []},
        "entrance":       {"near": ["town_square"],                             "far": []},
    },
    "interior": {
        "common_room":    {"near": ["entrance", "bar", "kitchen"],              "far": []},
        "kitchen":        {"near": ["common_room", "storage"],                  "far": []},
        "bar":            {"near": ["common_room"],                             "far": []},
        "guest_room":     {"near": ["common_room"],                             "far": ["cellar"]},
        "cellar":         {"near": ["storage", "kitchen"],                      "far": []},
        "entrance":       {"near": ["common_room"],                             "far": ["cellar"]},
    },
    "outdoor": {
        "entrance":       {"near": [],                                          "far": []},
        "shrine":         {"near": ["crypt"],                                   "far": []},
        "crypt":          {"near": ["shrine"],                                  "far": ["entrance"]},
    },
    "large_scale": {
        "entrance":       {"near": ["town_square"],                             "far": []},
        "town_square":    {"near": ["entrance", "shop"],                        "far": []},
    },
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_room_purposes.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
cd "C:/Dev/Map Generator"
git add mapgen_agents/data/room_purposes.py tests/test_room_purposes.py
git commit -m "feat: add room purpose definitions and adjacency rules"
```

---

## Task 4: Game Tables (XP, Treasure, Room Counts)

**Files:**
- Create: `mapgen_agents/data/game_tables.py`
- Test: `tests/test_game_tables.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_game_tables.py
"""Tests for D&D-derived game balance tables."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from data.game_tables import PARTY_XP_TABLE, TREASURE_TABLE, SIZE_ROOM_COUNTS


class TestPartyXpTable:
    def test_covers_levels_1_to_20(self):
        for level in range(1, 21):
            assert level in PARTY_XP_TABLE, f"Missing level {level}"

    def test_xp_increases_with_level(self):
        prev = 0
        for level in range(1, 21):
            assert PARTY_XP_TABLE[level] >= prev, f"Level {level} XP doesn't increase"
            prev = PARTY_XP_TABLE[level]

    def test_level_1_is_reasonable(self):
        assert 25 <= PARTY_XP_TABLE[1] <= 100


class TestTreasureTable:
    def test_covers_levels_1_to_20(self):
        for level in range(1, 21):
            assert level in TREASURE_TABLE, f"Missing level {level}"

    def test_treasure_increases_with_level(self):
        prev = 0
        for level in range(1, 21):
            assert TREASURE_TABLE[level] >= prev, f"Level {level} treasure doesn't increase"
            prev = TREASURE_TABLE[level]


class TestSizeRoomCounts:
    def test_all_sizes_present(self):
        sizes = ["small_encounter", "medium_encounter", "large_encounter", "standard", "large", "region", "open_world"]
        for size in sizes:
            assert size in SIZE_ROOM_COUNTS, f"Missing size {size}"

    def test_all_families_present(self):
        families = ["underground", "fortification", "settlement", "interior", "outdoor", "large_scale"]
        for size, counts in SIZE_ROOM_COUNTS.items():
            for family in families:
                assert family in counts, f"Missing {family} in {size}"

    def test_open_world_has_more_rooms_than_small(self):
        for family in ["underground", "fortification", "settlement"]:
            small = SIZE_ROOM_COUNTS["small_encounter"][family]
            big = SIZE_ROOM_COUNTS["open_world"][family]
            assert big > small, f"{family}: open_world should have more rooms than small_encounter"

    def test_minimum_room_count(self):
        for size, counts in SIZE_ROOM_COUNTS.items():
            for family, count in counts.items():
                assert count >= 3, f"{family}/{size} has fewer than 3 rooms"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_game_tables.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement game tables**

```python
# mapgen_agents/data/game_tables.py
"""D&D 5e-derived game balance tables for encounter and loot budgets."""

# XP threshold per player per level (based on D&D 5e "medium" encounter threshold).
# Multiply by party_size for total party XP budget.
PARTY_XP_TABLE: dict[int, int] = {
    1: 50,
    2: 100,
    3: 150,
    4: 250,
    5: 500,
    6: 600,
    7: 750,
    8: 900,
    9: 1100,
    10: 1200,
    11: 1600,
    12: 2000,
    13: 2200,
    14: 2500,
    15: 2800,
    16: 3200,
    17: 3900,
    18: 4200,
    19: 4900,
    20: 5700,
}

# Gold piece value per player per level for total dungeon treasure.
# Multiply by party_size and loot_tier multiplier.
TREASURE_TABLE: dict[int, int] = {
    1: 30,
    2: 60,
    3: 100,
    4: 175,
    5: 350,
    6: 500,
    7: 750,
    8: 1000,
    9: 1500,
    10: 2000,
    11: 3000,
    12: 4000,
    13: 5500,
    14: 7500,
    15: 10000,
    16: 13000,
    17: 17000,
    18: 22000,
    19: 28000,
    20: 40000,
}

# Base room count per map size and family. Jittered +/-20% at generation time.
SIZE_ROOM_COUNTS: dict[str, dict[str, int]] = {
    "small_encounter":  {"underground": 5,  "fortification": 4,  "settlement": 4,  "interior": 4,  "outdoor": 3,  "large_scale": 6},
    "medium_encounter": {"underground": 8,  "fortification": 6,  "settlement": 6,  "interior": 6,  "outdoor": 5,  "large_scale": 10},
    "large_encounter":  {"underground": 12, "fortification": 8,  "settlement": 8,  "interior": 8,  "outdoor": 7,  "large_scale": 15},
    "standard":         {"underground": 10, "fortification": 8,  "settlement": 8,  "interior": 7,  "outdoor": 6,  "large_scale": 12},
    "large":            {"underground": 16, "fortification": 12, "settlement": 12, "interior": 10, "outdoor": 10, "large_scale": 20},
    "region":           {"underground": 20, "fortification": 15, "settlement": 15, "interior": 12, "outdoor": 12, "large_scale": 30},
    "open_world":       {"underground": 25, "fortification": 20, "settlement": 20, "interior": 15, "outdoor": 15, "large_scale": 50},
}

# Loot tier -> difficulty multiplier (used for both XP and treasure budgets)
DIFFICULTY_MULT: dict[str, float] = {
    "low": 0.6,
    "medium": 1.0,
    "high": 1.5,
    "legendary": 2.0,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_game_tables.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
cd "C:/Dev/Map Generator"
git add mapgen_agents/data/game_tables.py tests/test_game_tables.py
git commit -m "feat: add D&D 5e game balance tables for encounters and loot"
```

---

## Task 5: Map Type Profiles

**Files:**
- Create: `mapgen_agents/pipeline/profiles.py`
- Test: `tests/test_profiles.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_profiles.py
"""Tests for map type profiles and family configuration."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from pipeline.profiles import MAP_TYPE_PROFILES, FAMILIES, get_profile, get_family


ALL_MAP_TYPES = [
    "dungeon", "cave", "mine", "maze", "crypt", "tomb",
    "castle", "fort", "tower", "outpost",
    "village", "town", "city", "camp", "rest_area",
    "tavern", "prison", "library", "throne_room", "shop",
    "shopping_center", "factory", "temple", "church", "treasure_room",
    "wilderness", "graveyard", "dock", "arena", "crash_site",
    "biomes", "region", "open_world", "world_box",
]

REQUIRED_PROFILE_KEYS = {
    "family", "topology_preference", "size_topology_override", "room_pool",
    "creature_table", "trap_density", "loot_tier", "dressing_palette",
    "biome_override", "z_levels", "corridor_style", "door_frequency",
    "secret_room_chance",
}

ALL_FAMILIES = ["underground", "fortification", "settlement", "interior", "outdoor", "large_scale"]


class TestProfiles:
    def test_all_map_types_present(self):
        for mt in ALL_MAP_TYPES:
            assert mt in MAP_TYPE_PROFILES, f"Missing profile for {mt}"

    def test_profile_has_required_keys(self):
        for mt, profile in MAP_TYPE_PROFILES.items():
            missing = REQUIRED_PROFILE_KEYS - profile.keys()
            assert not missing, f"{mt} missing keys: {missing}"

    def test_family_is_valid(self):
        for mt, profile in MAP_TYPE_PROFILES.items():
            assert profile["family"] in ALL_FAMILIES, f"{mt} has invalid family: {profile['family']}"

    def test_topology_preference_is_list(self):
        for mt, profile in MAP_TYPE_PROFILES.items():
            assert isinstance(profile["topology_preference"], list), f"{mt} topology_preference not a list"
            assert len(profile["topology_preference"]) >= 1, f"{mt} has empty topology_preference"

    def test_room_pool_has_required(self):
        for mt, profile in MAP_TYPE_PROFILES.items():
            pool = profile["room_pool"]
            assert "required" in pool, f"{mt} room_pool missing 'required'"
            assert "common" in pool, f"{mt} room_pool missing 'common'"
            assert len(pool["required"]) >= 1, f"{mt} has no required rooms"

    def test_trap_density_in_range(self):
        for mt, profile in MAP_TYPE_PROFILES.items():
            assert 0.0 <= profile["trap_density"] <= 1.0, f"{mt} trap_density out of range"

    def test_door_frequency_in_range(self):
        for mt, profile in MAP_TYPE_PROFILES.items():
            assert 0.0 <= profile["door_frequency"] <= 1.0, f"{mt} door_frequency out of range"

    def test_secret_room_chance_in_range(self):
        for mt, profile in MAP_TYPE_PROFILES.items():
            assert 0.0 <= profile["secret_room_chance"] <= 1.0, f"{mt} secret_room_chance out of range"

    def test_loot_tier_valid(self):
        valid_tiers = {"low", "medium", "high", "legendary"}
        for mt, profile in MAP_TYPE_PROFILES.items():
            assert profile["loot_tier"] in valid_tiers, f"{mt} has invalid loot_tier"

    def test_z_levels_valid(self):
        for mt, profile in MAP_TYPE_PROFILES.items():
            z = profile["z_levels"]
            assert z["min"] >= 1, f"{mt} z_levels.min < 1"
            assert z["max"] >= z["min"], f"{mt} z_levels.max < min"


class TestGetProfile:
    def test_known_type(self):
        profile = get_profile("dungeon")
        assert profile["family"] == "underground"

    def test_unknown_type_raises(self):
        with pytest.raises(KeyError):
            get_profile("nonexistent")


class TestGetFamily:
    def test_returns_family_name(self):
        assert get_family("dungeon") == "underground"
        assert get_family("village") == "settlement"
        assert get_family("tavern") == "interior"

class TestFamilies:
    def test_all_families_defined(self):
        for family in ALL_FAMILIES:
            assert family in FAMILIES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_profiles.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement profiles**

```python
# mapgen_agents/pipeline/profiles.py
"""Map type profiles and family configuration for the generation pipeline.

Each of the 30 map types is a data-driven profile dict. No per-type code.
Profiles are grouped into 6 families that define pipeline behavior.
"""

# Family pipeline configurations
FAMILIES: dict[str, dict] = {
    "underground": {
        "cave_carver": True,
        "terrain_preset": "dungeon",
        "corridor_default": "carved",
    },
    "fortification": {
        "cave_carver": False,
        "terrain_preset": None,  # uses requested biome
        "corridor_default": "built",
    },
    "settlement": {
        "cave_carver": False,
        "terrain_preset": None,
        "corridor_default": "road",
    },
    "interior": {
        "cave_carver": False,
        "terrain_preset": "flat_floor",
        "corridor_default": "hallway",
    },
    "outdoor": {
        "cave_carver": True,
        "terrain_preset": None,
        "corridor_default": "natural",
        "carve_threshold": 0.35,
        "passage_threshold": 0.40,
        "smoothing_iterations": 2,
    },
    "large_scale": {
        "cave_carver": True,
        "terrain_preset": None,
        "corridor_default": "road",
        "carve_threshold": 0.40,
        "passage_threshold": 0.45,
        "smoothing_iterations": 2,
    },
}


MAP_TYPE_PROFILES: dict[str, dict] = {
    # ── Underground ──────────────────────────────────────────────────
    "dungeon": {
        "family": "underground",
        "topology_preference": ["hub_and_spoke", "loop_based"],
        "size_topology_override": {"small_encounter": "linear_with_branches", "large": "hybrid"},
        "room_pool": {
            "required": ["entrance", "boss_lair"],
            "common": ["guard_room", "barracks", "armory", "storage", "cell"],
            "uncommon": ["shrine", "alchemy_lab", "library", "crypt"],
            "rare": ["treasure_vault", "secret_chamber", "portal_room"],
        },
        "creature_table": {
            "common": [("skeleton", 3), ("goblin", 2), ("rat", 2)],
            "uncommon": [("orc", 2), ("zombie", 1)],
            "boss": [("ogre", 1), ("troll", 1)],
        },
        "trap_density": 0.3,
        "loot_tier": "medium",
        "dressing_palette": "dungeon",
        "biome_override": "dungeon",
        "z_levels": {"min": 1, "max": 4},
        "corridor_style": "carved",
        "door_frequency": 0.6,
        "secret_room_chance": 0.15,
    },
    "cave": {
        "family": "underground",
        "topology_preference": ["linear_with_branches", "loop_based"],
        "size_topology_override": {"large": "hybrid"},
        "room_pool": {
            "required": ["entrance"],
            "common": ["storage", "cell"],
            "uncommon": ["shrine", "crypt"],
            "rare": ["treasure_vault", "secret_chamber"],
        },
        "creature_table": {
            "common": [("rat", 3), ("wolf", 2)],
            "uncommon": [("goblin", 2)],
            "boss": [("ogre", 1)],
        },
        "trap_density": 0.15,
        "loot_tier": "low",
        "dressing_palette": "dungeon",
        "biome_override": "cave",
        "z_levels": {"min": 1, "max": 3},
        "corridor_style": "natural",
        "door_frequency": 0.1,
        "secret_room_chance": 0.1,
    },
    "mine": {
        "family": "underground",
        "topology_preference": ["linear_with_branches"],
        "size_topology_override": {"large": "hub_and_spoke"},
        "room_pool": {
            "required": ["entrance"],
            "common": ["storage", "cell"],
            "uncommon": ["armory"],
            "rare": ["treasure_vault"],
        },
        "creature_table": {
            "common": [("goblin", 3), ("rat", 2)],
            "uncommon": [("orc", 1)],
            "boss": [("ogre", 1)],
        },
        "trap_density": 0.2,
        "loot_tier": "medium",
        "dressing_palette": "dungeon",
        "biome_override": "cave",
        "z_levels": {"min": 1, "max": 3},
        "corridor_style": "carved",
        "door_frequency": 0.2,
        "secret_room_chance": 0.1,
    },
    "maze": {
        "family": "underground",
        "topology_preference": ["loop_based"],
        "size_topology_override": {"small_encounter": "linear_with_branches"},
        "room_pool": {
            "required": ["entrance"],
            "common": ["corridor_hub"],
            "uncommon": ["shrine"],
            "rare": ["treasure_vault", "secret_chamber"],
        },
        "creature_table": {
            "common": [("skeleton", 2), ("zombie", 2)],
            "uncommon": [("orc", 1)],
            "boss": [("troll", 1)],
        },
        "trap_density": 0.4,
        "loot_tier": "medium",
        "dressing_palette": "dungeon",
        "biome_override": "dungeon",
        "z_levels": {"min": 1, "max": 1},
        "corridor_style": "carved",
        "door_frequency": 0.3,
        "secret_room_chance": 0.2,
    },
    "crypt": {
        "family": "underground",
        "topology_preference": ["linear_with_branches", "hub_and_spoke"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance", "boss_lair"],
            "common": ["crypt", "cell", "storage"],
            "uncommon": ["shrine", "library"],
            "rare": ["treasure_vault", "secret_chamber"],
        },
        "creature_table": {
            "common": [("skeleton", 4), ("zombie", 2)],
            "uncommon": [("orc", 1)],
            "boss": [("troll", 1)],
        },
        "trap_density": 0.35,
        "loot_tier": "medium",
        "dressing_palette": "dungeon",
        "biome_override": "dungeon",
        "z_levels": {"min": 1, "max": 3},
        "corridor_style": "carved",
        "door_frequency": 0.5,
        "secret_room_chance": 0.15,
    },
    "tomb": {
        "family": "underground",
        "topology_preference": ["linear_with_branches"],
        "size_topology_override": {"large": "hub_and_spoke"},
        "room_pool": {
            "required": ["entrance", "boss_lair"],
            "common": ["crypt", "guard_room", "storage"],
            "uncommon": ["shrine", "alchemy_lab", "treasure_vault"],
            "rare": ["secret_chamber", "portal_room"],
        },
        "creature_table": {
            "common": [("skeleton", 3), ("zombie", 2)],
            "uncommon": [("orc", 1)],
            "boss": [("troll", 1), ("ogre", 1)],
        },
        "trap_density": 0.4,
        "loot_tier": "high",
        "dressing_palette": "dungeon",
        "biome_override": "dungeon",
        "z_levels": {"min": 1, "max": 3},
        "corridor_style": "carved",
        "door_frequency": 0.7,
        "secret_room_chance": 0.2,
    },

    # ── Fortification ────────────────────────────────────────────────
    "castle": {
        "family": "fortification",
        "topology_preference": ["hub_and_spoke", "loop_based"],
        "size_topology_override": {"small_encounter": "linear_with_branches"},
        "room_pool": {
            "required": ["entrance", "boss_lair"],
            "common": ["guard_room", "barracks", "armory", "storage"],
            "uncommon": ["shrine", "library", "treasure_vault"],
            "rare": ["secret_chamber", "portal_room"],
        },
        "creature_table": {
            "common": [("guard", 4), ("bandit", 2)],
            "uncommon": [("orc", 2)],
            "boss": [("ogre", 1), ("troll", 1)],
        },
        "trap_density": 0.25,
        "loot_tier": "high",
        "dressing_palette": "fortification",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 5},
        "corridor_style": "built",
        "door_frequency": 0.8,
        "secret_room_chance": 0.1,
    },
    "fort": {
        "family": "fortification",
        "topology_preference": ["hub_and_spoke"],
        "size_topology_override": {"small_encounter": "linear_with_branches"},
        "room_pool": {
            "required": ["entrance"],
            "common": ["guard_room", "barracks", "armory", "storage"],
            "uncommon": ["shrine"],
            "rare": ["treasure_vault"],
        },
        "creature_table": {
            "common": [("guard", 3), ("bandit", 2)],
            "uncommon": [("orc", 1)],
            "boss": [("ogre", 1)],
        },
        "trap_density": 0.2,
        "loot_tier": "medium",
        "dressing_palette": "fortification",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 3},
        "corridor_style": "built",
        "door_frequency": 0.7,
        "secret_room_chance": 0.05,
    },
    "tower": {
        "family": "fortification",
        "topology_preference": ["linear_with_branches"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance", "boss_lair"],
            "common": ["guard_room", "library", "storage"],
            "uncommon": ["alchemy_lab", "shrine"],
            "rare": ["treasure_vault", "portal_room"],
        },
        "creature_table": {
            "common": [("guard", 2), ("skeleton", 2)],
            "uncommon": [("orc", 1)],
            "boss": [("troll", 1)],
        },
        "trap_density": 0.3,
        "loot_tier": "high",
        "dressing_palette": "fortification",
        "biome_override": None,
        "z_levels": {"min": 3, "max": 6},
        "corridor_style": "built",
        "door_frequency": 0.8,
        "secret_room_chance": 0.1,
    },
    "outpost": {
        "family": "fortification",
        "topology_preference": ["linear_with_branches"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance"],
            "common": ["guard_room", "barracks", "storage"],
            "uncommon": ["armory"],
            "rare": ["secret_chamber"],
        },
        "creature_table": {
            "common": [("guard", 2), ("bandit", 1)],
            "uncommon": [("orc", 1)],
            "boss": [],
        },
        "trap_density": 0.1,
        "loot_tier": "low",
        "dressing_palette": "fortification",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 2},
        "corridor_style": "built",
        "door_frequency": 0.6,
        "secret_room_chance": 0.05,
    },

    # ── Settlement ───────────────────────────────────────────────────
    "village": {
        "family": "settlement",
        "topology_preference": ["hub_and_spoke"],
        "size_topology_override": {"small_encounter": "linear_with_branches"},
        "room_pool": {
            "required": ["entrance", "town_square"],
            "common": ["house", "tavern", "shop", "farm", "well"],
            "uncommon": ["blacksmith", "inn", "stable"],
            "rare": ["manor", "hidden_cellar"],
        },
        "creature_table": {
            "common": [("rat", 2)],
            "uncommon": [("wolf", 1), ("bandit", 1)],
            "boss": [],
        },
        "trap_density": 0.0,
        "loot_tier": "low",
        "dressing_palette": "settlement",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 2},
        "corridor_style": "road",
        "door_frequency": 0.9,
        "secret_room_chance": 0.05,
    },
    "town": {
        "family": "settlement",
        "topology_preference": ["hub_and_spoke"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance", "town_square"],
            "common": ["house", "tavern", "shop", "inn"],
            "uncommon": ["blacksmith", "stable", "shrine"],
            "rare": ["manor", "hidden_cellar"],
        },
        "creature_table": {
            "common": [("rat", 2), ("bandit", 1)],
            "uncommon": [("guard", 1)],
            "boss": [],
        },
        "trap_density": 0.0,
        "loot_tier": "low",
        "dressing_palette": "settlement",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 2},
        "corridor_style": "road",
        "door_frequency": 0.9,
        "secret_room_chance": 0.05,
    },
    "city": {
        "family": "settlement",
        "topology_preference": ["hub_and_spoke", "loop_based"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance", "town_square"],
            "common": ["house", "tavern", "shop", "inn"],
            "uncommon": ["blacksmith", "shrine", "manor"],
            "rare": ["hidden_cellar", "secret_chamber"],
        },
        "creature_table": {
            "common": [("bandit", 2), ("guard", 2)],
            "uncommon": [("orc", 1)],
            "boss": [],
        },
        "trap_density": 0.05,
        "loot_tier": "medium",
        "dressing_palette": "settlement",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 3},
        "corridor_style": "road",
        "door_frequency": 0.9,
        "secret_room_chance": 0.05,
    },
    "camp": {
        "family": "settlement",
        "topology_preference": ["linear_with_branches"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance"],
            "common": ["storage", "safe_haven"],
            "uncommon": ["guard_room"],
            "rare": [],
        },
        "creature_table": {
            "common": [("rat", 1), ("wolf", 1)],
            "uncommon": [("bandit", 1)],
            "boss": [],
        },
        "trap_density": 0.0,
        "loot_tier": "low",
        "dressing_palette": "settlement",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 1},
        "corridor_style": "natural",
        "door_frequency": 0.2,
        "secret_room_chance": 0.0,
    },
    "rest_area": {
        "family": "settlement",
        "topology_preference": ["linear_with_branches"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance", "safe_haven"],
            "common": ["storage"],
            "uncommon": [],
            "rare": [],
        },
        "creature_table": {
            "common": [("rat", 1)],
            "uncommon": [],
            "boss": [],
        },
        "trap_density": 0.0,
        "loot_tier": "low",
        "dressing_palette": "settlement",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 1},
        "corridor_style": "natural",
        "door_frequency": 0.1,
        "secret_room_chance": 0.0,
    },

    # ── Interior ─────────────────────────────────────────────────────
    "tavern": {
        "family": "interior",
        "topology_preference": ["linear_with_branches"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance", "common_room"],
            "common": ["kitchen", "bar", "guest_room", "storage"],
            "uncommon": ["cellar", "owner_quarters", "stable"],
            "rare": ["secret_chamber", "gambling_den"],
        },
        "creature_table": {
            "common": [("rat", 1)],
            "uncommon": [("bandit", 2)],
            "boss": [],
        },
        "trap_density": 0.05,
        "loot_tier": "low",
        "dressing_palette": "tavern",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 2},
        "corridor_style": "hallway",
        "door_frequency": 0.95,
        "secret_room_chance": 0.1,
    },
    "prison": {
        "family": "interior",
        "topology_preference": ["linear_with_branches", "hub_and_spoke"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance"],
            "common": ["cell", "guard_room", "storage"],
            "uncommon": ["armory", "boss_lair"],
            "rare": ["secret_chamber", "treasure_vault"],
        },
        "creature_table": {
            "common": [("guard", 3), ("bandit", 2)],
            "uncommon": [("orc", 1)],
            "boss": [("ogre", 1)],
        },
        "trap_density": 0.15,
        "loot_tier": "medium",
        "dressing_palette": "dungeon",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 2},
        "corridor_style": "hallway",
        "door_frequency": 0.95,
        "secret_room_chance": 0.1,
    },
    "library": {
        "family": "interior",
        "topology_preference": ["linear_with_branches"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance"],
            "common": ["library", "storage"],
            "uncommon": ["shrine", "alchemy_lab"],
            "rare": ["secret_chamber", "treasure_vault"],
        },
        "creature_table": {
            "common": [("skeleton", 1)],
            "uncommon": [],
            "boss": [],
        },
        "trap_density": 0.15,
        "loot_tier": "medium",
        "dressing_palette": "dungeon",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 2},
        "corridor_style": "hallway",
        "door_frequency": 0.9,
        "secret_room_chance": 0.15,
    },
    "throne_room": {
        "family": "interior",
        "topology_preference": ["hub_and_spoke"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance", "boss_lair"],
            "common": ["guard_room", "storage"],
            "uncommon": ["armory", "treasure_vault"],
            "rare": ["secret_chamber"],
        },
        "creature_table": {
            "common": [("guard", 4)],
            "uncommon": [("orc", 1)],
            "boss": [("troll", 1)],
        },
        "trap_density": 0.2,
        "loot_tier": "high",
        "dressing_palette": "fortification",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 2},
        "corridor_style": "hallway",
        "door_frequency": 0.9,
        "secret_room_chance": 0.1,
    },
    "shop": {
        "family": "interior",
        "topology_preference": ["linear_with_branches"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance"],
            "common": ["storage", "shop"],
            "uncommon": ["owner_quarters"],
            "rare": ["secret_chamber"],
        },
        "creature_table": {
            "common": [("rat", 1)],
            "uncommon": [("bandit", 1)],
            "boss": [],
        },
        "trap_density": 0.05,
        "loot_tier": "low",
        "dressing_palette": "tavern",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 1},
        "corridor_style": "hallway",
        "door_frequency": 0.9,
        "secret_room_chance": 0.05,
    },
    "shopping_center": {
        "family": "interior",
        "topology_preference": ["hub_and_spoke"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance", "town_square"],
            "common": ["shop", "storage"],
            "uncommon": ["tavern", "blacksmith"],
            "rare": ["secret_chamber"],
        },
        "creature_table": {
            "common": [("bandit", 2), ("rat", 2)],
            "uncommon": [("guard", 1)],
            "boss": [],
        },
        "trap_density": 0.05,
        "loot_tier": "medium",
        "dressing_palette": "tavern",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 2},
        "corridor_style": "hallway",
        "door_frequency": 0.9,
        "secret_room_chance": 0.05,
    },
    "factory": {
        "family": "interior",
        "topology_preference": ["hub_and_spoke"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance"],
            "common": ["storage", "guard_room"],
            "uncommon": ["armory", "boss_lair"],
            "rare": ["secret_chamber"],
        },
        "creature_table": {
            "common": [("bandit", 2), ("guard", 1)],
            "uncommon": [("orc", 1)],
            "boss": [("ogre", 1)],
        },
        "trap_density": 0.1,
        "loot_tier": "medium",
        "dressing_palette": "dungeon",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 2},
        "corridor_style": "hallway",
        "door_frequency": 0.8,
        "secret_room_chance": 0.05,
    },
    "temple": {
        "family": "interior",
        "topology_preference": ["hub_and_spoke"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance", "shrine"],
            "common": ["library", "storage", "cell"],
            "uncommon": ["crypt", "alchemy_lab", "treasure_vault"],
            "rare": ["boss_lair", "secret_chamber", "portal_room"],
        },
        "creature_table": {
            "common": [("guard", 2), ("skeleton", 1)],
            "uncommon": [("orc", 1)],
            "boss": [("troll", 1)],
        },
        "trap_density": 0.2,
        "loot_tier": "medium",
        "dressing_palette": "dungeon",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 3},
        "corridor_style": "hallway",
        "door_frequency": 0.85,
        "secret_room_chance": 0.1,
    },
    "church": {
        "family": "interior",
        "topology_preference": ["linear_with_branches"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance", "shrine"],
            "common": ["library", "storage"],
            "uncommon": ["crypt"],
            "rare": ["secret_chamber"],
        },
        "creature_table": {
            "common": [("guard", 1)],
            "uncommon": [("skeleton", 1)],
            "boss": [],
        },
        "trap_density": 0.05,
        "loot_tier": "low",
        "dressing_palette": "dungeon",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 2},
        "corridor_style": "hallway",
        "door_frequency": 0.9,
        "secret_room_chance": 0.05,
    },
    "treasure_room": {
        "family": "interior",
        "topology_preference": ["linear_with_branches"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance", "treasure_vault"],
            "common": ["guard_room", "storage"],
            "uncommon": ["armory"],
            "rare": ["secret_chamber", "boss_lair"],
        },
        "creature_table": {
            "common": [("guard", 2)],
            "uncommon": [("orc", 2), ("ogre", 1)],
            "boss": [("troll", 1)],
        },
        "trap_density": 0.5,
        "loot_tier": "legendary",
        "dressing_palette": "dungeon",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 2},
        "corridor_style": "hallway",
        "door_frequency": 0.8,
        "secret_room_chance": 0.2,
    },

    # ── Outdoor ──────────────────────────────────────────────────────
    "wilderness": {
        "family": "outdoor",
        "topology_preference": ["linear_with_branches"],
        "size_topology_override": {"large": "hub_and_spoke"},
        "room_pool": {
            "required": ["entrance"],
            "common": ["safe_haven", "storage"],
            "uncommon": ["shrine"],
            "rare": ["secret_chamber", "treasure_vault"],
        },
        "creature_table": {
            "common": [("wolf", 3), ("rat", 2)],
            "uncommon": [("bandit", 2)],
            "boss": [("ogre", 1)],
        },
        "trap_density": 0.1,
        "loot_tier": "low",
        "dressing_palette": "outdoor",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 1},
        "corridor_style": "natural",
        "door_frequency": 0.0,
        "secret_room_chance": 0.1,
    },
    "graveyard": {
        "family": "outdoor",
        "topology_preference": ["linear_with_branches"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance"],
            "common": ["crypt", "shrine"],
            "uncommon": ["guard_room"],
            "rare": ["treasure_vault", "secret_chamber", "boss_lair"],
        },
        "creature_table": {
            "common": [("zombie", 3), ("skeleton", 2)],
            "uncommon": [("orc", 1)],
            "boss": [("troll", 1)],
        },
        "trap_density": 0.15,
        "loot_tier": "medium",
        "dressing_palette": "outdoor",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 2},
        "corridor_style": "natural",
        "door_frequency": 0.3,
        "secret_room_chance": 0.1,
    },
    "dock": {
        "family": "outdoor",
        "topology_preference": ["linear_with_branches"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance"],
            "common": ["storage", "shop"],
            "uncommon": ["tavern", "guard_room"],
            "rare": ["secret_chamber"],
        },
        "creature_table": {
            "common": [("bandit", 2), ("rat", 2)],
            "uncommon": [("guard", 1)],
            "boss": [],
        },
        "trap_density": 0.05,
        "loot_tier": "low",
        "dressing_palette": "outdoor",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 1},
        "corridor_style": "natural",
        "door_frequency": 0.3,
        "secret_room_chance": 0.05,
    },
    "arena": {
        "family": "outdoor",
        "topology_preference": ["hub_and_spoke"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance", "arena"],
            "common": ["guard_room", "storage"],
            "uncommon": ["armory", "cell"],
            "rare": ["treasure_vault", "boss_lair"],
        },
        "creature_table": {
            "common": [("gladiator", 2), ("guard", 2)],
            "uncommon": [("orc", 2)],
            "boss": [("ogre", 1), ("troll", 1)],
        },
        "trap_density": 0.1,
        "loot_tier": "medium",
        "dressing_palette": "outdoor",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 1},
        "corridor_style": "built",
        "door_frequency": 0.5,
        "secret_room_chance": 0.05,
    },
    "crash_site": {
        "family": "outdoor",
        "topology_preference": ["linear_with_branches"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance"],
            "common": ["storage"],
            "uncommon": ["treasure_vault"],
            "rare": ["secret_chamber"],
        },
        "creature_table": {
            "common": [("rat", 2), ("wolf", 1)],
            "uncommon": [("bandit", 2)],
            "boss": [],
        },
        "trap_density": 0.1,
        "loot_tier": "medium",
        "dressing_palette": "outdoor",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 1},
        "corridor_style": "natural",
        "door_frequency": 0.1,
        "secret_room_chance": 0.1,
    },

    # ── Large-scale ──────────────────────────────────────────────────
    "biomes": {
        "family": "large_scale",
        "topology_preference": ["hub_and_spoke"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance", "town_square"],
            "common": ["house", "shop", "safe_haven"],
            "uncommon": ["shrine", "tavern"],
            "rare": ["treasure_vault", "boss_lair"],
        },
        "creature_table": {
            "common": [("wolf", 2), ("bandit", 2)],
            "uncommon": [("orc", 1)],
            "boss": [("ogre", 1)],
        },
        "trap_density": 0.1,
        "loot_tier": "medium",
        "dressing_palette": "outdoor",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 1},
        "corridor_style": "road",
        "door_frequency": 0.3,
        "secret_room_chance": 0.05,
    },
    "region": {
        "family": "large_scale",
        "topology_preference": ["hub_and_spoke", "loop_based"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance", "town_square"],
            "common": ["house", "shop", "tavern", "safe_haven"],
            "uncommon": ["shrine", "guard_room", "blacksmith"],
            "rare": ["treasure_vault", "boss_lair", "secret_chamber"],
        },
        "creature_table": {
            "common": [("wolf", 2), ("bandit", 2), ("guard", 1)],
            "uncommon": [("orc", 2)],
            "boss": [("ogre", 1), ("troll", 1)],
        },
        "trap_density": 0.1,
        "loot_tier": "medium",
        "dressing_palette": "outdoor",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 2},
        "corridor_style": "road",
        "door_frequency": 0.3,
        "secret_room_chance": 0.05,
    },
    "open_world": {
        "family": "large_scale",
        "topology_preference": ["hybrid"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance"],
            "common": ["town_square", "house", "shop", "tavern", "safe_haven"],
            "uncommon": ["shrine", "guard_room", "blacksmith", "boss_lair"],
            "rare": ["treasure_vault", "secret_chamber", "portal_room"],
        },
        "creature_table": {
            "common": [("wolf", 2), ("bandit", 2), ("guard", 2)],
            "uncommon": [("orc", 2), ("goblin", 2)],
            "boss": [("ogre", 1), ("troll", 1)],
        },
        "trap_density": 0.1,
        "loot_tier": "medium",
        "dressing_palette": "outdoor",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 3},
        "corridor_style": "road",
        "door_frequency": 0.3,
        "secret_room_chance": 0.1,
    },
    "world_box": {
        "family": "large_scale",
        "topology_preference": ["hybrid"],
        "size_topology_override": {},
        "room_pool": {
            "required": ["entrance"],
            "common": ["town_square", "house", "shop", "tavern", "safe_haven"],
            "uncommon": ["shrine", "guard_room", "boss_lair"],
            "rare": ["treasure_vault", "secret_chamber", "portal_room"],
        },
        "creature_table": {
            "common": [("wolf", 2), ("bandit", 2), ("guard", 2)],
            "uncommon": [("orc", 2), ("goblin", 2)],
            "boss": [("ogre", 1), ("troll", 1)],
        },
        "trap_density": 0.1,
        "loot_tier": "medium",
        "dressing_palette": "outdoor",
        "biome_override": None,
        "z_levels": {"min": 1, "max": 3},
        "corridor_style": "road",
        "door_frequency": 0.3,
        "secret_room_chance": 0.1,
    },
}


def get_profile(map_type: str) -> dict:
    """Look up a map type profile. Raises KeyError if not found."""
    return MAP_TYPE_PROFILES[map_type]


def get_family(map_type: str) -> str:
    """Return the family name for a map type."""
    return MAP_TYPE_PROFILES[map_type]["family"]
```

- [ ] **Step 4: Update pipeline __init__.py**

Add to `mapgen_agents/pipeline/__init__.py`:

```python
from pipeline.generation_request import GenerationRequest
from pipeline.profiles import get_profile, get_family, MAP_TYPE_PROFILES, FAMILIES

__all__ = ["GenerationRequest", "get_profile", "get_family", "MAP_TYPE_PROFILES", "FAMILIES"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_profiles.py -v`
Expected: 13 passed

- [ ] **Step 6: Commit**

```bash
cd "C:/Dev/Map Generator"
git add mapgen_agents/pipeline/profiles.py mapgen_agents/pipeline/__init__.py tests/test_profiles.py
git commit -m "feat: add all 30 map type profiles and family configs"
```

---

## Task 6: SharedState Enhancements

**Files:**
- Modify: `mapgen_agents/shared_state.py`
- Test: `tests/test_zlevel.py` (extend existing)

- [ ] **Step 1: Write failing test**

Add to the end of `tests/test_zlevel.py`:

```python
class TestSharedStatePipelineFields:
    """Tests for new pipeline-related fields on SharedState."""

    def test_cave_mask_initialized_none(self):
        config = MapConfig(width=64, height=64, biome="dungeon", map_type="dungeon", seed=1)
        state = SharedState(config)
        assert state.cave_mask is None

    def test_cave_mask_settable(self):
        config = MapConfig(width=64, height=64, biome="dungeon", map_type="dungeon", seed=1)
        state = SharedState(config)
        mask = np.zeros((64, 64), dtype=bool)
        state.cave_mask = mask
        assert state.cave_mask is not None
        assert state.cave_mask.shape == (64, 64)

    def test_natural_openings_initialized_empty(self):
        config = MapConfig(width=64, height=64, biome="dungeon", map_type="dungeon", seed=1)
        state = SharedState(config)
        assert state.natural_openings == []

    def test_room_graph_initialized_none(self):
        config = MapConfig(width=64, height=64, biome="dungeon", map_type="dungeon", seed=1)
        state = SharedState(config)
        assert state.room_graph is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_zlevel.py::TestSharedStatePipelineFields -v`
Expected: FAIL — `AttributeError: 'SharedState' object has no attribute 'cave_mask'`

- [ ] **Step 3: Add fields to SharedState.__init__**

In `mapgen_agents/shared_state.py`, add after line 143 (`"agents_completed": [],`), before the closing `}`:

```python
        # Pipeline fields (populated by generation pipeline agents)
        self.cave_mask: np.ndarray | None = None
        self.natural_openings: list[tuple[int, int, int, int]] = []  # (x, y, w, h)
        self.room_graph = None  # RoomGraph, set by TopologyAgent
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_zlevel.py -v`
Expected: All tests pass (existing + new)

- [ ] **Step 5: Commit**

```bash
cd "C:/Dev/Map Generator"
git add mapgen_agents/shared_state.py tests/test_zlevel.py
git commit -m "feat: add cave_mask, natural_openings, room_graph fields to SharedState"
```

---

## Task 7: TerrainAgent Enhancements

**Files:**
- Modify: `mapgen_agents/agents/terrain_agent.py`
- Test: `tests/test_terrain_enhanced.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_terrain_enhanced.py
"""Tests for TerrainAgent pipeline enhancements."""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from agents.terrain_agent import TerrainAgent, BIOME_PRESETS


class TestNewBiomePresets:
    def test_flat_floor_preset_exists(self):
        assert "flat_floor" in BIOME_PRESETS

    def test_flat_floor_produces_flat_elevation(self):
        config = MapConfig(width=64, height=64, biome="flat_floor", map_type="tavern", seed=42)
        state = SharedState(config)
        agent = TerrainAgent()
        agent.execute(state, {"biome": "flat_floor"})
        # Flat floor should have very low elevation variance
        assert state.elevation.std() < 0.05
        # Should be mostly walkable
        assert state.walkability.mean() > 0.95

    def test_road_ready_preset_exists(self):
        assert "road_ready" in BIOME_PRESETS


class TestRawNoiseExposure:
    def test_raw_elevation_stored_in_metadata(self):
        config = MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42)
        state = SharedState(config)
        agent = TerrainAgent()
        agent.execute(state, {"biome": "forest"})
        assert "raw_elevation" in state.metadata
        assert isinstance(state.metadata["raw_elevation"], np.ndarray)
        assert state.metadata["raw_elevation"].shape == (64, 64)

    def test_raw_elevation_is_pre_modification(self):
        config = MapConfig(width=64, height=64, biome="cave", map_type="cave", seed=42)
        state = SharedState(config)
        agent = TerrainAgent()
        agent.execute(state, {"biome": "cave"})
        raw = state.metadata["raw_elevation"]
        # Raw should be unmodified noise (0-1 range, varied)
        assert raw.min() >= 0.0
        assert raw.max() <= 1.0
        assert raw.std() > 0.05  # not flat
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_terrain_enhanced.py -v`
Expected: FAIL — missing presets and raw_elevation

- [ ] **Step 3: Add new presets and raw noise storage**

In `mapgen_agents/agents/terrain_agent.py`, add to `BIOME_PRESETS` dict after the `"sky"` entry:

```python
    "flat_floor": {
        "elevation_scale": 500, "elevation_octaves": 1,
        "moisture_scale": 500, "moisture_base": 0.3,
        "walkability_threshold": 0.99,
    },
    "road_ready": {
        "elevation_scale": 150, "elevation_octaves": 3,
        "moisture_scale": 80, "moisture_base": 0.4,
        "walkability_threshold": 0.92,
    },
```

In the `_run` method of `TerrainAgent`, add after generating elevation (after line 242) and before generating moisture:

```python
        # Store raw elevation for CaveCarverAgent consumption
        shared_state.metadata["raw_elevation"] = shared_state.elevation.copy()
```

For `flat_floor` biome, override elevation to near-constant after generation. Add before the `# For dungeon/cave` block:

```python
        # Flat floor: override to near-constant elevation for interior maps
        if biome == "flat_floor":
            shared_state.elevation = np.full((h, w), 0.3, dtype=np.float32)
            # Add very subtle variation for visual interest
            shared_state.elevation += perlin_noise_2d((h, w), scale=500, seed=seed, octaves=1) * 0.02
            shared_state.walkability[:] = True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_terrain_enhanced.py -v`
Expected: 5 passed

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/ -v`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
cd "C:/Dev/Map Generator"
git add mapgen_agents/agents/terrain_agent.py tests/test_terrain_enhanced.py
git commit -m "feat: add flat_floor/road_ready presets, expose raw noise for CaveCarver"
```

---

## Task 8: CaveCarverAgent

**Files:**
- Create: `mapgen_agents/agents/cave_carver_agent.py`
- Test: `tests/test_cave_carver.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_cave_carver.py
"""Tests for CaveCarverAgent — noise-threshold carving + cellular automata."""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from agents.terrain_agent import TerrainAgent
from agents.cave_carver_agent import CaveCarverAgent


def make_state_with_terrain(biome="dungeon", map_type="dungeon", seed=42, size=128):
    """Helper: create SharedState and run TerrainAgent to populate elevation."""
    config = MapConfig(width=size, height=size, biome=biome, map_type=map_type, seed=seed)
    state = SharedState(config)
    TerrainAgent().execute(state, {"biome": biome})
    return state


class TestCaveCarverBasics:
    def test_produces_cave_mask(self):
        state = make_state_with_terrain()
        CaveCarverAgent().execute(state, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        assert state.cave_mask is not None
        assert state.cave_mask.shape == (128, 128)
        assert state.cave_mask.dtype == bool

    def test_cave_mask_has_open_space(self):
        state = make_state_with_terrain()
        CaveCarverAgent().execute(state, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        open_pct = state.cave_mask.mean()
        assert open_pct > 0.05, "Cave should have some open space"
        assert open_pct < 0.95, "Cave should have some solid rock"

    def test_natural_openings_detected(self):
        state = make_state_with_terrain()
        CaveCarverAgent().execute(state, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        assert isinstance(state.natural_openings, list)
        # Should find at least one large opening in a 128x128 map
        assert len(state.natural_openings) >= 1

    def test_natural_openings_format(self):
        state = make_state_with_terrain()
        CaveCarverAgent().execute(state, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        for opening in state.natural_openings:
            assert len(opening) == 4, "Opening should be (x, y, w, h)"
            x, y, w, h = opening
            assert w > 0 and h > 0


class TestCaveCarverConnectivity:
    def test_single_connected_region(self):
        """After carving, all open space should be one connected region."""
        state = make_state_with_terrain(seed=42)
        CaveCarverAgent().execute(state, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        # Flood fill from first open tile
        mask = state.cave_mask.copy()
        open_tiles = np.argwhere(mask)
        if len(open_tiles) == 0:
            pytest.skip("No open tiles carved")

        start_y, start_x = open_tiles[0]
        visited = np.zeros_like(mask)
        stack = [(start_y, start_x)]
        visited[start_y, start_x] = True
        count = 0
        while stack:
            cy, cx = stack.pop()
            count += 1
            for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1]:
                    if mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        stack.append((ny, nx))
        total_open = mask.sum()
        assert count == total_open, f"Expected single region ({total_open} tiles), flood fill found {count}"


class TestCaveCarverSmoothing:
    def test_smoothing_reduces_isolated_pixels(self):
        """Cellular automata should eliminate single-pixel noise."""
        state = make_state_with_terrain(seed=100)
        CaveCarverAgent().execute(state, {
            "carve_threshold": 0.45,
            "passage_threshold": 0.50,
            "smoothing_iterations": 3,
        })
        mask = state.cave_mask
        # Count isolated open pixels (open tile with all 4 neighbors solid)
        isolated = 0
        h, w = mask.shape
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if mask[y, x]:
                    neighbors_open = mask[y-1, x] + mask[y+1, x] + mask[y, x-1] + mask[y, x+1]
                    if neighbors_open == 0:
                        isolated += 1
        assert isolated == 0, f"Found {isolated} isolated open pixels after smoothing"


class TestCaveCarverSkip:
    def test_skip_when_not_needed(self):
        """Families that don't need carving should produce no cave_mask."""
        state = make_state_with_terrain(biome="forest", map_type="village")
        result = CaveCarverAgent().execute(state, {"skip": True})
        assert state.cave_mask is None
        assert result["details"]["skipped"] is True


class TestCaveCarverDeterminism:
    def test_same_seed_same_result(self):
        state1 = make_state_with_terrain(seed=42)
        state2 = make_state_with_terrain(seed=42)
        CaveCarverAgent().execute(state1, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        CaveCarverAgent().execute(state2, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        np.testing.assert_array_equal(state1.cave_mask, state2.cave_mask)

    def test_different_seed_different_result(self):
        state1 = make_state_with_terrain(seed=42)
        state2 = make_state_with_terrain(seed=999)
        CaveCarverAgent().execute(state1, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        CaveCarverAgent().execute(state2, {"carve_threshold": 0.45, "passage_threshold": 0.50})
        assert not np.array_equal(state1.cave_mask, state2.cave_mask)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_cave_carver.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents.cave_carver_agent'`

- [ ] **Step 3: Implement CaveCarverAgent**

```python
# mapgen_agents/agents/cave_carver_agent.py
"""
CaveCarverAgent — Carves natural cavities from terrain noise using threshold + cellular automata.

Phase 1 agent. Reads raw_elevation from SharedState metadata (stored by TerrainAgent),
applies dual-threshold carving, smooths with cellular automata, validates connectivity
via flood fill, and writes cave_mask + natural_openings to SharedState.
"""

import numpy as np
from base_agent import BaseAgent
from shared_state import SharedState
from typing import Any


class CaveCarverAgent(BaseAgent):
    name = "CaveCarverAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        if params.get("skip", False):
            return {"skipped": True}

        seed = shared_state.config.seed
        h, w = shared_state.config.height, shared_state.config.width
        rng = np.random.default_rng(seed + 700)

        carve_threshold = params.get("carve_threshold", 0.45)
        passage_threshold = params.get("passage_threshold", 0.50)
        smoothing_iterations = params.get("smoothing_iterations", 3)
        min_pocket_size = params.get("min_pocket_size", 15)

        # Get raw elevation from TerrainAgent (pre-modification noise)
        raw_elevation = shared_state.metadata.get("raw_elevation")
        if raw_elevation is None:
            raw_elevation = shared_state.elevation.copy()

        # Generate secondary noise layer at different frequency
        secondary = self._generate_secondary_noise(h, w, seed, rng)

        # Dual-threshold carving
        cave_mask = (raw_elevation < carve_threshold) & (secondary < passage_threshold)

        # Cellular automata smoothing (B678/S345678 rule)
        cave_mask = self._smooth_cellular_automata(cave_mask, smoothing_iterations)

        # Flood fill: keep only largest connected region, fill small pockets
        cave_mask = self._enforce_connectivity(cave_mask, min_pocket_size)

        # Detect natural openings (large cavern centers)
        openings = self._detect_openings(cave_mask)

        # Write results to shared state
        shared_state.cave_mask = cave_mask
        shared_state.natural_openings = openings

        open_pct = float(cave_mask.mean() * 100)
        return {
            "skipped": False,
            "open_pct": round(open_pct, 1),
            "openings_found": len(openings),
            "smoothing_iterations": smoothing_iterations,
        }

    def _generate_secondary_noise(self, h: int, w: int, seed: int,
                                   rng: np.random.Generator) -> np.ndarray:
        """Generate a secondary noise layer at different frequency for passage variation."""
        # Use value noise at a different scale than the primary elevation
        grid_h = max(2, h // 8)
        grid_w = max(2, w // 8)
        gradients = rng.random((grid_h + 1, grid_w + 1)).astype(np.float32)

        y_coords = np.linspace(0, grid_h - 1, h)
        x_coords = np.linspace(0, grid_w - 1, w)
        y_grid, x_grid = np.meshgrid(y_coords, x_coords, indexing='ij')

        y0 = np.floor(y_grid).astype(int)
        x0 = np.floor(x_grid).astype(int)
        y1 = np.minimum(y0 + 1, grid_h)
        x1 = np.minimum(x0 + 1, grid_w)
        fy = y_grid - y0
        fx = x_grid - x0

        # Smoothstep interpolation
        fy = fy * fy * (3 - 2 * fy)
        fx = fx * fx * (3 - 2 * fx)

        top = gradients[y0, x0] * (1 - fx) + gradients[y0, x1] * fx
        bot = gradients[y1, x0] * (1 - fx) + gradients[y1, x1] * fx
        noise = top * (1 - fy) + bot * fy

        return noise

    def _smooth_cellular_automata(self, mask: np.ndarray, iterations: int) -> np.ndarray:
        """Apply B678/S345678 cellular automata to smooth cave edges.

        A dead cell (solid) becomes alive (open) if it has 6, 7, or 8 alive neighbors.
        An alive cell (open) stays alive if it has 3, 4, 5, 6, 7, or 8 alive neighbors.
        """
        h, w = mask.shape
        for _ in range(iterations):
            # Count neighbors using convolution-like approach with numpy
            padded = np.pad(mask.astype(np.int8), 1, mode='constant', constant_values=0)
            neighbor_count = (
                padded[:-2, :-2] + padded[:-2, 1:-1] + padded[:-2, 2:] +
                padded[1:-1, :-2]                      + padded[1:-1, 2:] +
                padded[2:, :-2]  + padded[2:, 1:-1]   + padded[2:, 2:]
            )
            # B678: dead cell becomes alive with 6+ neighbors
            born = (~mask) & (neighbor_count >= 6)
            # S345678: alive cell survives with 3+ neighbors
            survive = mask & (neighbor_count >= 3)
            mask = born | survive

        # Force edges to be solid (walls around the map)
        mask[0, :] = False
        mask[-1, :] = False
        mask[:, 0] = False
        mask[:, -1] = False

        return mask

    def _enforce_connectivity(self, mask: np.ndarray, min_pocket_size: int) -> np.ndarray:
        """Keep only the largest connected region. Fill small isolated pockets."""
        h, w = mask.shape
        visited = np.zeros((h, w), dtype=bool)
        regions: list[list[tuple[int, int]]] = []

        for sy in range(h):
            for sx in range(w):
                if mask[sy, sx] and not visited[sy, sx]:
                    # Flood fill this region
                    region = []
                    stack = [(sy, sx)]
                    visited[sy, sx] = True
                    while stack:
                        cy, cx = stack.pop()
                        region.append((cy, cx))
                        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w:
                                if mask[ny, nx] and not visited[ny, nx]:
                                    visited[ny, nx] = True
                                    stack.append((ny, nx))
                    regions.append(region)

        if not regions:
            return mask

        # Keep only the largest region
        largest = max(regions, key=len)
        largest_set = set(largest)

        # Clear mask and repaint only the largest region
        result = np.zeros_like(mask)
        for y, x in largest:
            result[y, x] = True

        return result

    def _detect_openings(self, mask: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Find large open areas (natural cavern openings) in the cave mask.

        Returns list of (x, y, width, height) bounding boxes for openings
        larger than a minimum threshold.
        """
        h, w = mask.shape
        visited = np.zeros((h, w), dtype=bool)
        openings = []
        min_opening_area = max(20, (h * w) // 200)  # at least 0.5% of map or 20 tiles

        for sy in range(h):
            for sx in range(w):
                if mask[sy, sx] and not visited[sy, sx]:
                    # Flood fill to find contiguous open area
                    region_ys = []
                    region_xs = []
                    stack = [(sy, sx)]
                    visited[sy, sx] = True
                    while stack:
                        cy, cx = stack.pop()
                        region_ys.append(cy)
                        region_xs.append(cx)
                        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w:
                                if mask[ny, nx] and not visited[ny, nx]:
                                    visited[ny, nx] = True
                                    stack.append((ny, nx))

                    if len(region_ys) >= min_opening_area:
                        min_y, max_y = min(region_ys), max(region_ys)
                        min_x, max_x = min(region_xs), max(region_xs)
                        openings.append((
                            min_x,
                            min_y,
                            max_x - min_x + 1,
                            max_y - min_y + 1,
                        ))

        return openings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_cave_carver.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
cd "C:/Dev/Map Generator"
git add mapgen_agents/agents/cave_carver_agent.py tests/test_cave_carver.py
git commit -m "feat: add CaveCarverAgent with noise carving + cellular automata + flood fill"
```

---

## Task 9: Phase Validation Functions

**Files:**
- Create: `mapgen_agents/pipeline/validation.py`
- Test: `tests/test_validation.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_validation.py
"""Tests for pipeline phase validation functions."""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from pipeline.validation import validate_terrain, ValidationResult


class TestValidationResult:
    def test_passed(self):
        r = ValidationResult(passed=True, errors=[])
        assert r.passed is True
        assert r.errors == []

    def test_failed(self):
        r = ValidationResult(passed=False, errors=["not enough walkable area"])
        assert r.passed is False
        assert len(r.errors) == 1


class TestValidateTerrain:
    def test_good_terrain_passes(self):
        config = MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42)
        state = SharedState(config)
        # Set up valid terrain: mostly walkable, no water partition
        state.walkability[:] = True
        state.water_mask[:] = False
        result = validate_terrain(state, family="settlement", min_walkable_pct=0.2)
        assert result.passed is True

    def test_insufficient_walkable_area_fails(self):
        config = MapConfig(width=64, height=64, biome="dungeon", map_type="dungeon", seed=42)
        state = SharedState(config)
        state.walkability[:] = False  # nothing walkable
        result = validate_terrain(state, family="underground", min_walkable_pct=0.1)
        assert result.passed is False
        assert any("walkable" in e.lower() for e in result.errors)

    def test_cave_mask_has_open_space(self):
        config = MapConfig(width=64, height=64, biome="dungeon", map_type="dungeon", seed=42)
        state = SharedState(config)
        state.walkability[:] = True
        state.cave_mask = np.zeros((64, 64), dtype=bool)  # no open space
        result = validate_terrain(state, family="underground", min_walkable_pct=0.1)
        assert result.passed is False
        assert any("cave" in e.lower() for e in result.errors)

    def test_cave_mask_not_checked_for_settlements(self):
        config = MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42)
        state = SharedState(config)
        state.walkability[:] = True
        state.cave_mask = None  # no cave mask for settlements — that's fine
        result = validate_terrain(state, family="settlement", min_walkable_pct=0.1)
        assert result.passed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_validation.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement validation**

```python
# mapgen_agents/pipeline/validation.py
"""Phase validation functions for the generation pipeline."""

from dataclasses import dataclass, field
import numpy as np
from shared_state import SharedState

CAVE_FAMILIES = {"underground", "outdoor", "large_scale"}


@dataclass
class ValidationResult:
    passed: bool
    errors: list[str] = field(default_factory=list)


def validate_terrain(state: SharedState, family: str,
                     min_walkable_pct: float = 0.1) -> ValidationResult:
    """Validate Phase 1 (Terrain) output.

    Checks:
    - Walkable area >= min_walkable_pct of total map
    - For cave families: cave_mask has open space (> 5% of map)
    """
    errors = []
    h, w = state.config.height, state.config.width
    total_tiles = h * w

    # Check walkable area
    walkable_pct = float(state.walkability.sum()) / total_tiles
    if walkable_pct < min_walkable_pct:
        errors.append(
            f"Insufficient walkable area: {walkable_pct:.1%} < {min_walkable_pct:.1%} required"
        )

    # Check cave mask for families that use carving
    if family in CAVE_FAMILIES:
        if state.cave_mask is None:
            errors.append(f"Cave mask missing for {family} family (expected carving)")
        else:
            cave_open_pct = float(state.cave_mask.sum()) / total_tiles
            if cave_open_pct < 0.05:
                errors.append(
                    f"Cave mask has insufficient open space: {cave_open_pct:.1%} < 5% required"
                )

    return ValidationResult(passed=len(errors) == 0, errors=errors)


def validate_layout(state: SharedState) -> ValidationResult:
    """Validate Phase 2 (Layout) output. Stub for Phase 2 plan."""
    # Will check: all rooms reachable, entrance→boss path, zone count, no orphaned corridors
    return ValidationResult(passed=True, errors=[])


def validate_population(state: SharedState) -> ValidationResult:
    """Validate Phase 3 (Population) output. Stub for Phase 3 plan."""
    # Will check: XP budget, loot budget, room dressing, boss encounter, player spawn
    return ValidationResult(passed=True, errors=[])
```

- [ ] **Step 4: Update pipeline __init__.py**

```python
# mapgen_agents/pipeline/__init__.py
from pipeline.generation_request import GenerationRequest
from pipeline.profiles import get_profile, get_family, MAP_TYPE_PROFILES, FAMILIES
from pipeline.validation import validate_terrain, validate_layout, validate_population, ValidationResult

__all__ = [
    "GenerationRequest", "get_profile", "get_family",
    "MAP_TYPE_PROFILES", "FAMILIES",
    "validate_terrain", "validate_layout", "validate_population", "ValidationResult",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_validation.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
cd "C:/Dev/Map Generator"
git add mapgen_agents/pipeline/validation.py mapgen_agents/pipeline/__init__.py tests/test_validation.py
git commit -m "feat: add phase validation functions with terrain checks"
```

---

## Task 10: PipelineCoordinator

**Files:**
- Create: `mapgen_agents/pipeline/coordinator.py`
- Test: `tests/test_pipeline_coordinator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_pipeline_coordinator.py
"""Tests for PipelineCoordinator — 3-phase orchestration with validation."""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from pipeline.coordinator import PipelineCoordinator
from pipeline.generation_request import GenerationRequest
from shared_state import SharedState


class TestPipelineCoordinatorInit:
    def test_creates_shared_state(self):
        req = GenerationRequest(
            map_type="dungeon", biome="dungeon", size="standard", seed=42,
            party_level=5, party_size=4,
        )
        coord = PipelineCoordinator(req)
        assert coord.request is req
        assert coord.profile["family"] == "underground"
        assert coord.family == "underground"

    def test_resolves_biome_override(self):
        req = GenerationRequest(
            map_type="dungeon", biome="forest", size="standard", seed=42,
        )
        coord = PipelineCoordinator(req)
        # Dungeon profile has biome_override="dungeon", should override forest
        assert coord.effective_biome == "dungeon"

    def test_no_biome_override(self):
        req = GenerationRequest(
            map_type="village", biome="forest", size="standard", seed=42,
        )
        coord = PipelineCoordinator(req)
        assert coord.effective_biome == "forest"


class TestPhase1Execution:
    def test_phase1_produces_terrain(self):
        req = GenerationRequest(
            map_type="village", biome="forest", size="small_encounter", seed=42,
        )
        coord = PipelineCoordinator(req)
        result = coord.run_phase1()
        assert result.passed is True
        state = coord.shared_state
        assert state.elevation is not None
        assert state.moisture is not None
        assert state.terrain_color is not None

    def test_phase1_runs_cave_carver_for_underground(self):
        req = GenerationRequest(
            map_type="dungeon", biome="dungeon", size="small_encounter", seed=42,
        )
        coord = PipelineCoordinator(req)
        result = coord.run_phase1()
        assert result.passed is True
        assert coord.shared_state.cave_mask is not None

    def test_phase1_skips_cave_carver_for_settlements(self):
        req = GenerationRequest(
            map_type="village", biome="forest", size="small_encounter", seed=42,
        )
        coord = PipelineCoordinator(req)
        result = coord.run_phase1()
        assert result.passed is True
        assert coord.shared_state.cave_mask is None

    def test_phase1_uses_flat_floor_for_interior(self):
        req = GenerationRequest(
            map_type="tavern", biome="forest", size="small_encounter", seed=42,
        )
        coord = PipelineCoordinator(req)
        result = coord.run_phase1()
        assert result.passed is True
        # Interior should have very flat terrain
        assert coord.shared_state.elevation.std() < 0.05


class TestFullPipeline:
    def test_generate_returns_shared_state(self):
        req = GenerationRequest(
            map_type="dungeon", biome="dungeon", size="small_encounter", seed=42,
            party_level=3, party_size=4,
        )
        coord = PipelineCoordinator(req)
        state = coord.generate()
        assert isinstance(state, SharedState)
        assert state.config.map_type == "dungeon"
        assert state.config.seed == 42

    def test_deterministic_generation(self):
        req1 = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=42)
        req2 = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=42)
        state1 = PipelineCoordinator(req1).generate()
        state2 = PipelineCoordinator(req2).generate()
        np.testing.assert_array_equal(state1.elevation, state2.elevation)

    def test_different_seeds_produce_different_maps(self):
        req1 = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=42)
        req2 = GenerationRequest(map_type="dungeon", biome="dungeon", size="small_encounter", seed=999)
        state1 = PipelineCoordinator(req1).generate()
        state2 = PipelineCoordinator(req2).generate()
        assert not np.array_equal(state1.elevation, state2.elevation)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_pipeline_coordinator.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement PipelineCoordinator**

```python
# mapgen_agents/pipeline/coordinator.py
"""PipelineCoordinator — Orchestrates 3-phase map generation with validation and retry.

Phase 1 (Terrain): TerrainAgent → WaterAgent → CaveCarverAgent
Phase 2 (Layout): TopologyAgent → StructureAgent → ConnectorAgent → PathfindingAgent
Phase 3 (Population): RoomPurposeAgent → EncounterAgent → TrapAgent → LootAgent → DressingAgent → SpawnAgent

Phases 2 and 3 are stubs in this implementation — they pass through to existing
agents for backwards compatibility. They will be replaced in Plans 2 and 3.
"""

from shared_state import SharedState, MapConfig
from pipeline.generation_request import GenerationRequest
from pipeline.profiles import get_profile, FAMILIES
from pipeline.validation import (
    validate_terrain, validate_layout, validate_population, ValidationResult,
)
from agents.terrain_agent import TerrainAgent
from agents.water_agent import WaterAgent
from agents.cave_carver_agent import CaveCarverAgent

# Map size preset → (width, height)
SIZE_DIMENSIONS: dict[str, tuple[int, int]] = {
    "small_encounter": (256, 256),
    "medium_encounter": (512, 512),
    "large_encounter": (768, 768),
    "standard": (512, 512),
    "large": (1024, 1024),
    "region": (1024, 1024),
    "open_world": (1536, 1536),
}

MAX_RETRIES = 3


class PipelineCoordinator:
    """Orchestrates the 3-phase generation pipeline."""

    def __init__(self, request: GenerationRequest):
        self.request = request
        self.profile = get_profile(request.map_type)
        self.family = self.profile["family"]
        self.family_config = FAMILIES[self.family]

        # Resolve effective biome (profile can override requested biome)
        biome_override = self.profile.get("biome_override")
        self.effective_biome = biome_override if biome_override else request.biome

        # Resolve map dimensions from size preset
        width, height = SIZE_DIMENSIONS[request.size]

        # Create SharedState
        config = MapConfig(
            width=width,
            height=height,
            biome=self.effective_biome,
            map_type=request.map_type,
            seed=request.seed,
        )
        self.shared_state = SharedState(config)

    def generate(self) -> SharedState:
        """Run the full 3-phase pipeline. Returns populated SharedState."""
        # Phase 1: Terrain
        for attempt in range(MAX_RETRIES):
            result = self.run_phase1()
            if result.passed:
                break
            # Relax constraints on retry
            if attempt < MAX_RETRIES - 1:
                self.shared_state.metadata["terrain_retry"] = attempt + 1

        # Phase 2: Layout (stub — passes through to existing agents in Plan 2)
        self.run_phase2()

        # Phase 3: Population (stub — passes through to existing agents in Plan 3)
        self.run_phase3()

        return self.shared_state

    def run_phase1(self) -> ValidationResult:
        """Execute Phase 1: Terrain generation + cave carving."""
        state = self.shared_state

        # Determine terrain biome based on family
        terrain_biome = self.effective_biome
        if self.family_config.get("terrain_preset") == "flat_floor":
            terrain_biome = "flat_floor"

        # Run TerrainAgent
        TerrainAgent().execute(state, {"biome": terrain_biome})

        # Run WaterAgent (skip for interior/underground families that don't need hydrology)
        if self.family not in ("interior", "underground"):
            WaterAgent().execute(state, {"biome": terrain_biome})

        # Run CaveCarverAgent if family uses carving
        if self.family_config.get("cave_carver", False):
            CaveCarverAgent().execute(state, {
                "carve_threshold": self.family_config.get("carve_threshold", 0.45),
                "passage_threshold": self.family_config.get("passage_threshold", 0.50),
                "smoothing_iterations": self.family_config.get("smoothing_iterations", 3),
            })
        else:
            CaveCarverAgent().execute(state, {"skip": True})

        # Validate
        min_walkable = 0.05 if self.family == "underground" else 0.2
        return validate_terrain(state, family=self.family, min_walkable_pct=min_walkable)

    def run_phase2(self) -> ValidationResult:
        """Execute Phase 2: Layout. Stub — will be implemented in Plan 2."""
        return validate_layout(self.shared_state)

    def run_phase3(self) -> ValidationResult:
        """Execute Phase 3: Population. Stub — will be implemented in Plan 3."""
        return validate_population(self.shared_state)
```

- [ ] **Step 4: Update pipeline __init__.py**

```python
# mapgen_agents/pipeline/__init__.py
from pipeline.generation_request import GenerationRequest
from pipeline.profiles import get_profile, get_family, MAP_TYPE_PROFILES, FAMILIES
from pipeline.validation import validate_terrain, validate_layout, validate_population, ValidationResult
from pipeline.coordinator import PipelineCoordinator

__all__ = [
    "GenerationRequest", "PipelineCoordinator",
    "get_profile", "get_family", "MAP_TYPE_PROFILES", "FAMILIES",
    "validate_terrain", "validate_layout", "validate_population", "ValidationResult",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/test_pipeline_coordinator.py -v`
Expected: 8 passed

- [ ] **Step 6: Run full test suite**

Run: `cd "C:/Dev/Map Generator" && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
cd "C:/Dev/Map Generator"
git add mapgen_agents/pipeline/coordinator.py mapgen_agents/pipeline/__init__.py tests/test_pipeline_coordinator.py
git commit -m "feat: add PipelineCoordinator with Phase 1 terrain orchestration"
```

---

## Milestone: Phase 1 Complete

At this point, the following is working and tested:

- **GenerationRequest** — typed input to the pipeline
- **RoomGraph** — abstract room connectivity graph (used by Phase 2)
- **Room purposes** — 35 purpose definitions with gameplay multipliers + adjacency rules for 6 families
- **Game tables** — D&D 5e XP/treasure tables for levels 1-20, room counts per size/family
- **34 map type profiles** — all data-driven, all validated
- **SharedState enhancements** — cave_mask, natural_openings, room_graph fields
- **TerrainAgent enhancements** — flat_floor/road_ready presets, raw noise exposure
- **CaveCarverAgent** — noise-threshold carving + cellular automata + flood fill connectivity
- **Phase validation** — terrain validation with family-aware checks
- **PipelineCoordinator** — 3-phase orchestration with Phase 1 fully wired, Phases 2-3 stubbed

**Next:** Phase 2 plan (TopologyAgent, ConnectorAgent, StructureAgent/PathfindingAgent enhancements)

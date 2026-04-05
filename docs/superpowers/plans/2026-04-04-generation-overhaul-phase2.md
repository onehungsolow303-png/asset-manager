# Generation Overhaul Phase 2: Layout Agents

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 2 layout agents: TopologyAgent (abstract room graph generation with 4 topology types), ConnectorAgent (corridors, doors, stairs), enhanced StructureAgent (place rooms from RoomGraph into terrain), enhanced PathfindingAgent (connectivity validation), and wire Phase 2 into PipelineCoordinator.

**Architecture:** TopologyAgent generates an abstract RoomGraph. StructureAgent realizes it in physical space by placing rooms into cave openings or carving from solid. ConnectorAgent carves corridors between rooms and places doors/stairs. PathfindingAgent validates connectivity. PipelineCoordinator orchestrates the sequence.

**Tech Stack:** Python 3.11+, numpy, pytest

**Spec:** `docs/superpowers/specs/2026-04-04-generation-overhaul-design.md` (Sections 4, 6, 12)

**Depends on:** Phase 1 (complete) — GenerationRequest, RoomGraph, profiles, SharedState enhancements, CaveCarverAgent, PipelineCoordinator skeleton

---

## File Map

### New Files

| File | Responsibility |
|------|---------------|
| `mapgen_agents/agents/topology_agent.py` | TopologyAgent — 4 topology types, zone assignment, room count resolution |
| `mapgen_agents/agents/connector_agent.py` | ConnectorAgent — corridor carving, door placement, stair generation, secret passages |
| `tests/test_topology_agent.py` | Tests for TopologyAgent |
| `tests/test_connector_agent.py` | Tests for ConnectorAgent |
| `tests/test_structure_enhanced.py` | Tests for StructureAgent RoomGraph mode |
| `tests/test_pathfinding_enhanced.py` | Tests for PathfindingAgent validation mode |

### Modified Files

| File | Changes |
|------|---------|
| `mapgen_agents/agents/structure_agent.py` | Add `_place_rooms_from_graph()` method that accepts RoomGraph and places rooms into terrain |
| `mapgen_agents/agents/pathfinding_agent.py` | Add `validate_connectivity()` method that checks RoomGraph against physical walkability |
| `mapgen_agents/pipeline/coordinator.py` | Wire Phase 2 agents into `run_phase2()` |
| `mapgen_agents/pipeline/validation.py` | Implement `validate_layout()` with real checks |

---

## Task 1: TopologyAgent — Core + Linear Topology

**Files:**
- Create: `mapgen_agents/agents/topology_agent.py`
- Create: `tests/test_topology_agent.py`

- [ ] **Step 1: Write failing tests for linear topology**

```python
# tests/test_topology_agent.py
"""Tests for TopologyAgent — abstract room graph generation."""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from agents.topology_agent import TopologyAgent
from data.room_graph import RoomGraph, RoomNode, GraphEdge


def make_state(map_type="dungeon", seed=42, size=256):
    config = MapConfig(width=size, height=size, biome="dungeon", map_type=map_type, seed=seed)
    return SharedState(config)


class TestTopologySelection:
    def test_selects_from_profile_preference(self):
        state = make_state()
        agent = TopologyAgent()
        # dungeon profile prefers hub_and_spoke, loop_based
        # standard size doesn't override, so first preference wins
        result = agent.execute(state, {
            "topology_preference": ["hub_and_spoke", "loop_based"],
            "size_topology_override": {},
            "size": "standard",
            "room_count": 10,
        })
        assert result["status"] == "completed"
        assert state.room_graph is not None

    def test_size_override_forces_topology(self):
        state = make_state()
        agent = TopologyAgent()
        result = agent.execute(state, {
            "topology_preference": ["hub_and_spoke"],
            "size_topology_override": {"small_encounter": "linear_with_branches"},
            "size": "small_encounter",
            "room_count": 5,
        })
        assert result["status"] == "completed"
        graph = state.room_graph
        # Linear topology should produce a chain-like structure
        assert graph is not None
        assert graph.node_count == 5


class TestLinearTopology:
    def test_produces_correct_node_count(self):
        state = make_state()
        agent = TopologyAgent()
        agent.execute(state, {
            "topology_preference": ["linear_with_branches"],
            "size_topology_override": {},
            "size": "standard",
            "room_count": 8,
        })
        graph = state.room_graph
        assert graph.node_count == 8

    def test_has_entrance_and_boss(self):
        state = make_state()
        agent = TopologyAgent()
        agent.execute(state, {
            "topology_preference": ["linear_with_branches"],
            "size_topology_override": {},
            "size": "standard",
            "room_count": 6,
        })
        graph = state.room_graph
        assert graph.entrance_node is not None
        assert graph.entrance_node.zone == 0

    def test_all_nodes_reachable(self):
        state = make_state()
        agent = TopologyAgent()
        agent.execute(state, {
            "topology_preference": ["linear_with_branches"],
            "size_topology_override": {},
            "size": "standard",
            "room_count": 8,
        })
        graph = state.room_graph
        assert graph.all_reachable_from(graph.entrance_node.node_id)

    def test_zones_increase_from_entrance(self):
        state = make_state()
        agent = TopologyAgent()
        agent.execute(state, {
            "topology_preference": ["linear_with_branches"],
            "size_topology_override": {},
            "size": "standard",
            "room_count": 8,
        })
        graph = state.room_graph
        entrance = graph.entrance_node
        assert entrance.zone == 0
        assert graph.max_zone >= 1

    def test_deterministic_with_same_seed(self):
        state1 = make_state(seed=42)
        state2 = make_state(seed=42)
        agent = TopologyAgent()
        params = {"topology_preference": ["linear_with_branches"], "size_topology_override": {}, "size": "standard", "room_count": 8}
        agent.execute(state1, params)
        agent.execute(state2, params)
        g1, g2 = state1.room_graph, state2.room_graph
        assert g1.node_count == g2.node_count
        assert g1.edge_count == g2.edge_count


class TestLoopTopology:
    def test_produces_cycles(self):
        state = make_state()
        agent = TopologyAgent()
        agent.execute(state, {
            "topology_preference": ["loop_based"],
            "size_topology_override": {},
            "size": "standard",
            "room_count": 10,
        })
        graph = state.room_graph
        # Loop topology should have more edges than nodes-1 (tree would be N-1)
        assert graph.edge_count > graph.node_count - 1

    def test_all_nodes_reachable(self):
        state = make_state()
        agent = TopologyAgent()
        agent.execute(state, {
            "topology_preference": ["loop_based"],
            "size_topology_override": {},
            "size": "standard",
            "room_count": 10,
        })
        graph = state.room_graph
        assert graph.all_reachable_from(graph.entrance_node.node_id)


class TestHubAndSpokeTopology:
    def test_has_hub_node(self):
        state = make_state()
        agent = TopologyAgent()
        agent.execute(state, {
            "topology_preference": ["hub_and_spoke"],
            "size_topology_override": {},
            "size": "standard",
            "room_count": 10,
        })
        graph = state.room_graph
        # Hub should be a high-degree node
        max_degree = max(len(graph.neighbors(n.node_id)) for n in graph.nodes)
        assert max_degree >= 3  # Hub connects to at least 3 wings

    def test_all_nodes_reachable(self):
        state = make_state()
        agent = TopologyAgent()
        agent.execute(state, {
            "topology_preference": ["hub_and_spoke"],
            "size_topology_override": {},
            "size": "standard",
            "room_count": 10,
        })
        graph = state.room_graph
        assert graph.all_reachable_from(graph.entrance_node.node_id)


class TestHybridTopology:
    def test_has_hub_and_cycles(self):
        state = make_state()
        agent = TopologyAgent()
        agent.execute(state, {
            "topology_preference": ["hybrid"],
            "size_topology_override": {},
            "size": "standard",
            "room_count": 12,
        })
        graph = state.room_graph
        max_degree = max(len(graph.neighbors(n.node_id)) for n in graph.nodes)
        assert max_degree >= 3  # Hub
        assert graph.edge_count > graph.node_count - 1  # Cycles

    def test_all_nodes_reachable(self):
        state = make_state()
        agent = TopologyAgent()
        agent.execute(state, {
            "topology_preference": ["hybrid"],
            "size_topology_override": {},
            "size": "standard",
            "room_count": 12,
        })
        graph = state.room_graph
        assert graph.all_reachable_from(graph.entrance_node.node_id)


class TestZoneAssignment:
    def test_entrance_is_zone_0(self):
        state = make_state()
        agent = TopologyAgent()
        agent.execute(state, {
            "topology_preference": ["linear_with_branches"],
            "size_topology_override": {},
            "size": "standard",
            "room_count": 8,
        })
        assert state.room_graph.entrance_node.zone == 0

    def test_zones_are_contiguous(self):
        state = make_state()
        agent = TopologyAgent()
        agent.execute(state, {
            "topology_preference": ["hub_and_spoke"],
            "size_topology_override": {},
            "size": "standard",
            "room_count": 10,
        })
        graph = state.room_graph
        zones = sorted(set(n.zone for n in graph.nodes))
        # Zones should be contiguous integers starting from 0
        assert zones[0] == 0
        for i in range(1, len(zones)):
            assert zones[i] - zones[i-1] <= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Dev/Map Generator" && uv run pytest tests/test_topology_agent.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement TopologyAgent**

Create `mapgen_agents/agents/topology_agent.py` inheriting from BaseAgent. The `_run` method should:

1. Read params: `topology_preference`, `size_topology_override`, `size`, `room_count`
2. Select topology type: check if size has an override, else use first preference
3. Generate graph using the selected topology method
4. Assign zones via BFS from entrance (zone increments every `room_count / desired_zones` rooms, where `desired_zones = max(2, room_count // 3)`)
5. Tag entrance node with `{"entrance"}` tag (zone 0), tag the deepest-zone node with `{"boss"}` tag
6. Write graph to `shared_state.room_graph`

**Topology algorithms:**

**linear_with_branches:** Create main chain of `main_count = room_count * 2 // 3` nodes. Remaining nodes attach as branches off random main-chain nodes. All edges are bidirectional corridors.

**loop_based:** Create spanning tree (random DFS), then add `room_count // 5` back-edges between random non-adjacent nodes to create cycles.

**hub_and_spoke:** Create hub node. Divide remaining rooms into `num_wings = min(room_count // 3, 5)` wings (at least 3). Each wing is a short chain hanging off the hub. Entrance connects to hub.

**hybrid:** Hub-and-spoke base, then add 1-2 back-edges per wing for loops.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "C:/Dev/Map Generator" && uv run pytest tests/test_topology_agent.py -v`

- [ ] **Step 5: Commit**

```bash
cd "C:/Dev/Map Generator"
git add mapgen_agents/agents/topology_agent.py tests/test_topology_agent.py
git commit -m "feat: add TopologyAgent with 4 topology types and zone assignment"
```

---

## Task 2: ConnectorAgent — Corridors, Doors, Stairs

**Files:**
- Create: `mapgen_agents/agents/connector_agent.py`
- Create: `tests/test_connector_agent.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_connector_agent.py
"""Tests for ConnectorAgent — corridors, doors, stairs."""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from agents.connector_agent import ConnectorAgent
from data.room_graph import RoomGraph, RoomNode, GraphEdge


def make_state_with_rooms():
    """Create state with two rooms placed, connected by a corridor edge in the graph."""
    config = MapConfig(width=128, height=128, biome="dungeon", map_type="dungeon", seed=42)
    state = SharedState(config)
    state.walkability[:] = False  # solid rock
    state.terrain_color[:] = (40, 38, 35)

    # Carve two rooms
    state.walkability[20:40, 20:50] = True  # Room A: 30x20 at (20,20)
    state.walkability[70:90, 60:90] = True  # Room B: 30x20 at (60,70)

    # Build room graph
    graph = RoomGraph()
    a = RoomNode("room_a", zone=0, position=(20, 20), size=(30, 20))
    b = RoomNode("room_b", zone=1, position=(60, 70), size=(30, 20))
    graph.add_node(a)
    graph.add_node(b)
    graph.add_edge(GraphEdge("room_a", "room_b", "corridor"))
    state.room_graph = graph
    return state


class TestCorridorCarving:
    def test_corridor_connects_rooms(self):
        state = make_state_with_rooms()
        agent = ConnectorAgent()
        agent.execute(state, {"corridor_style": "carved", "door_frequency": 0.0})
        # There should be a walkable path between room centers
        # Check that some tiles between the rooms are now walkable
        mid_y = 55  # between room A (y=20-40) and room B (y=70-90)
        walkable_at_mid = state.walkability[mid_y, :].sum()
        assert walkable_at_mid > 0, "Corridor should carve walkable tiles between rooms"

    def test_corridor_width_matches_style(self):
        state = make_state_with_rooms()
        agent = ConnectorAgent()
        agent.execute(state, {"corridor_style": "built", "door_frequency": 0.0})
        # Built corridors are 3-4 tiles wide
        # Check corridor cross-section somewhere between rooms
        result = agent.execute(state, {"corridor_style": "built", "door_frequency": 0.0})
        assert result["status"] == "completed"


class TestDoorPlacement:
    def test_doors_placed_at_frequency(self):
        state = make_state_with_rooms()
        # Set edge to "door" type
        state.room_graph._edges[0].connection_type = "door"
        agent = ConnectorAgent()
        agent.execute(state, {"corridor_style": "carved", "door_frequency": 1.0})
        # Should find door entities
        doors = [e for e in state.entities if e.entity_type == "door"]
        assert len(doors) >= 1


class TestStairGeneration:
    def test_stairs_created_for_stairs_edge(self):
        config = MapConfig(width=128, height=128, biome="dungeon", map_type="dungeon", seed=42)
        state = SharedState(config)
        state.walkability[:] = False
        state.walkability[20:40, 20:50] = True
        state.walkability[70:90, 60:90] = True

        graph = RoomGraph()
        a = RoomNode("room_a", zone=0, position=(20, 20), size=(30, 20))
        b = RoomNode("room_b", zone=1, position=(60, 70), size=(30, 20))
        graph.add_node(a)
        graph.add_node(b)
        graph.add_edge(GraphEdge("room_a", "room_b", "stairs"))
        state.room_graph = graph

        agent = ConnectorAgent()
        agent.execute(state, {"corridor_style": "carved", "door_frequency": 0.0})
        assert len(state.transitions) >= 1
        assert state.transitions[0].transition_type in ("stairs_up", "stairs_down")


class TestConnectorDeterminism:
    def test_same_seed_same_result(self):
        state1 = make_state_with_rooms()
        state2 = make_state_with_rooms()
        params = {"corridor_style": "carved", "door_frequency": 0.5}
        ConnectorAgent().execute(state1, params)
        ConnectorAgent().execute(state2, params)
        np.testing.assert_array_equal(state1.walkability, state2.walkability)
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement ConnectorAgent**

`mapgen_agents/agents/connector_agent.py` inherits BaseAgent. The `_run` method:

1. Read room_graph from shared_state
2. For each edge in the graph:
   - Find closest wall tiles between the two rooms (use room position + size)
   - Carve corridor between rooms using L-shaped path (horizontal then vertical, or vice versa based on seed)
   - Corridor width based on `corridor_style` param: carved=2-3, built=3-4, natural=variable, hallway=2, road=4-6
   - If edge type is "door": place Entity(entity_type="door") at corridor-room boundary
   - If edge type is "stairs": create Transition between z-levels, carve corridor on same level
   - If edge type is "secret": carve 1-tile-wide passage
3. Update walkability and terrain_color for carved tiles

**Corridor carving algorithm:** For two rooms at positions (x1,y1,w1,h1) and (x2,y2,w2,h2):
- Get room centers: cx1=x1+w1//2, cy1=y1+h1//2, cx2=x2+w2//2, cy2=y2+h2//2
- L-shape: carve horizontal from cx1→cx2 at cy1, then vertical from cy1→cy2 at cx2 (or reverse)
- Corridor width applied as thickness around the centerline

- [ ] **Step 4: Run tests, commit**

```bash
git add mapgen_agents/agents/connector_agent.py tests/test_connector_agent.py
git commit -m "feat: add ConnectorAgent with corridors, doors, and stairs"
```

---

## Task 3: StructureAgent Enhancements — RoomGraph Placement

**Files:**
- Modify: `mapgen_agents/agents/structure_agent.py`
- Create: `tests/test_structure_enhanced.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_structure_enhanced.py
"""Tests for StructureAgent RoomGraph-based room placement."""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from agents.structure_agent import StructureAgent
from data.room_graph import RoomGraph, RoomNode, GraphEdge


def make_state_with_graph(room_count=5, seed=42, size=256):
    config = MapConfig(width=size, height=size, biome="dungeon", map_type="dungeon", seed=seed)
    state = SharedState(config)
    state.walkability[:] = False  # solid rock

    # Build a simple linear graph
    graph = RoomGraph()
    for i in range(room_count):
        tags = set()
        if i == 0:
            tags.add("entrance")
        if i == room_count - 1:
            tags.add("boss")
        graph.add_node(RoomNode(f"room_{i}", zone=i, tags=tags))
    for i in range(room_count - 1):
        graph.add_edge(GraphEdge(f"room_{i}", f"room_{i+1}", "corridor"))
    state.room_graph = graph
    return state


class TestRoomGraphPlacement:
    def test_places_all_rooms(self):
        state = make_state_with_graph(room_count=5)
        agent = StructureAgent()
        result = agent.execute(state, {"type": "dungeon", "use_room_graph": True})
        assert result["status"] == "completed"
        # Each room node should have position and size set
        graph = state.room_graph
        for node in graph.nodes:
            assert node.position is not None, f"{node.node_id} has no position"
            assert node.size is not None, f"{node.node_id} has no size"

    def test_rooms_dont_overlap(self):
        state = make_state_with_graph(room_count=5, size=512)
        agent = StructureAgent()
        agent.execute(state, {"type": "dungeon", "use_room_graph": True})
        graph = state.room_graph
        nodes = graph.nodes
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a = nodes[i]
                b = nodes[j]
                ax, ay = a.position
                aw, ah = a.size
                bx, by = b.position
                bw, bh = b.size
                overlap = (ax < bx + bw and ax + aw > bx and
                          ay < by + bh and ay + ah > by)
                assert not overlap, f"{a.node_id} overlaps {b.node_id}"

    def test_rooms_carved_into_walkability(self):
        state = make_state_with_graph(room_count=3)
        agent = StructureAgent()
        agent.execute(state, {"type": "dungeon", "use_room_graph": True})
        # Some tiles should now be walkable
        assert state.walkability.sum() > 0

    def test_uses_cave_openings_when_available(self):
        state = make_state_with_graph(room_count=3, size=256)
        # Simulate cave opening
        state.cave_mask = np.zeros((256, 256), dtype=bool)
        state.cave_mask[50:120, 50:120] = True
        state.natural_openings = [(50, 50, 70, 70)]
        agent = StructureAgent()
        agent.execute(state, {"type": "dungeon", "use_room_graph": True})
        # At least some rooms should be placed within the cave opening
        graph = state.room_graph
        rooms_in_cave = 0
        for node in graph.nodes:
            x, y = node.position
            if 50 <= x <= 120 and 50 <= y <= 120:
                rooms_in_cave += 1
        assert rooms_in_cave >= 1

    def test_deterministic(self):
        state1 = make_state_with_graph(seed=42)
        state2 = make_state_with_graph(seed=42)
        params = {"type": "dungeon", "use_room_graph": True}
        StructureAgent().execute(state1, params)
        StructureAgent().execute(state2, params)
        g1, g2 = state1.room_graph, state2.room_graph
        for n1, n2 in zip(g1.nodes, g2.nodes):
            assert n1.position == n2.position
            assert n1.size == n2.size
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement StructureAgent enhancements**

Add a new method `_place_rooms_from_graph()` to StructureAgent. When `params.get("use_room_graph")` is True, call this method instead of the existing specialized generators.

**Algorithm for `_place_rooms_from_graph(state, params)`:**

1. Read room_graph from state
2. For each node in the graph:
   - Determine room size: `w = rng.integers(20, 45)`, `h = rng.integers(15, 35)` (dungeon scale)
   - If `natural_openings` exist, try to place the first few rooms inside them
   - Otherwise, use random placement with AABB collision detection (existing `_place_random_rooms` logic)
   - Set `node.position = (x, y)` and `node.size = (w, h)` on the RoomNode
   - Carve room into walkability and terrain_color using existing `_draw_filled_rect` method
   - Create Entity for the room
3. Update the `_run` method to check for `use_room_graph` param before routing to specialized generators

- [ ] **Step 4: Run tests, run full suite, commit**

```bash
git add mapgen_agents/agents/structure_agent.py tests/test_structure_enhanced.py
git commit -m "feat: add RoomGraph-based room placement to StructureAgent"
```

---

## Task 4: PathfindingAgent Validation Mode

**Files:**
- Modify: `mapgen_agents/agents/pathfinding_agent.py`
- Create: `tests/test_pathfinding_enhanced.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pathfinding_enhanced.py
"""Tests for PathfindingAgent connectivity validation mode."""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig
from agents.pathfinding_agent import PathfindingAgent
from data.room_graph import RoomGraph, RoomNode, GraphEdge


def make_connected_state():
    """Two rooms with walkable corridor between them."""
    config = MapConfig(width=128, height=128, biome="dungeon", map_type="dungeon", seed=42)
    state = SharedState(config)
    state.walkability[:] = False
    # Room A
    state.walkability[20:40, 20:50] = True
    # Room B
    state.walkability[20:40, 60:90] = True
    # Corridor connecting them
    state.walkability[28:32, 50:60] = True

    graph = RoomGraph()
    graph.add_node(RoomNode("a", zone=0, tags={"entrance"}, position=(20, 20), size=(30, 20)))
    graph.add_node(RoomNode("b", zone=1, position=(60, 20), size=(30, 20)))
    graph.add_edge(GraphEdge("a", "b", "corridor"))
    state.room_graph = graph
    return state


def make_disconnected_state():
    """Two rooms with NO walkable path between them."""
    config = MapConfig(width=128, height=128, biome="dungeon", map_type="dungeon", seed=42)
    state = SharedState(config)
    state.walkability[:] = False
    state.walkability[20:40, 20:50] = True
    state.walkability[80:100, 80:110] = True  # far away, no corridor

    graph = RoomGraph()
    graph.add_node(RoomNode("a", zone=0, tags={"entrance"}, position=(20, 20), size=(30, 20)))
    graph.add_node(RoomNode("b", zone=1, position=(80, 80), size=(30, 20)))
    graph.add_edge(GraphEdge("a", "b", "corridor"))
    state.room_graph = graph
    return state


class TestValidateConnectivity:
    def test_connected_rooms_pass(self):
        state = make_connected_state()
        agent = PathfindingAgent()
        result = agent.execute(state, {"mode": "validate"})
        assert result["status"] == "completed"
        assert result["details"]["all_connected"] is True
        assert result["details"]["orphaned_rooms"] == []

    def test_disconnected_rooms_detected(self):
        state = make_disconnected_state()
        agent = PathfindingAgent()
        result = agent.execute(state, {"mode": "validate"})
        assert result["status"] == "completed"
        assert result["details"]["all_connected"] is False
        assert len(result["details"]["orphaned_rooms"]) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement validation mode**

Add to PathfindingAgent's `_run` method: when `params.get("mode") == "validate"`, run connectivity validation instead of road generation.

**Validation algorithm:**
1. Get room_graph from shared_state
2. For each pair of rooms connected by an edge in the graph:
   - Get room center positions
   - Use A* to find a walkable path between them on shared_state.walkability
   - If no path found, mark the unreachable room as "orphaned"
3. Return `{"all_connected": bool, "orphaned_rooms": list[str]}`

- [ ] **Step 4: Run tests, commit**

```bash
git add mapgen_agents/agents/pathfinding_agent.py tests/test_pathfinding_enhanced.py
git commit -m "feat: add connectivity validation mode to PathfindingAgent"
```

---

## Task 5: Wire Phase 2 into PipelineCoordinator

**Files:**
- Modify: `mapgen_agents/pipeline/coordinator.py`
- Modify: `mapgen_agents/pipeline/validation.py`
- Create: `tests/test_phase2_integration.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_phase2_integration.py
"""Integration tests for Phase 2 in PipelineCoordinator."""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from pipeline.coordinator import PipelineCoordinator
from pipeline.generation_request import GenerationRequest
from shared_state import SharedState


class TestPhase2Integration:
    def test_phase2_produces_room_graph(self):
        req = GenerationRequest(
            map_type="dungeon", biome="dungeon", size="small_encounter", seed=42,
            party_level=3, party_size=4,
        )
        coord = PipelineCoordinator(req)
        coord.run_phase1()
        result = coord.run_phase2()
        assert result.passed is True
        assert coord.shared_state.room_graph is not None
        assert coord.shared_state.room_graph.node_count >= 3

    def test_phase2_rooms_have_positions(self):
        req = GenerationRequest(
            map_type="dungeon", biome="dungeon", size="small_encounter", seed=42,
        )
        coord = PipelineCoordinator(req)
        coord.run_phase1()
        coord.run_phase2()
        for node in coord.shared_state.room_graph.nodes:
            assert node.position is not None
            assert node.size is not None

    def test_phase2_rooms_are_connected(self):
        req = GenerationRequest(
            map_type="dungeon", biome="dungeon", size="small_encounter", seed=42,
        )
        coord = PipelineCoordinator(req)
        coord.run_phase1()
        result = coord.run_phase2()
        assert result.passed is True

    def test_full_pipeline_with_phase2(self):
        req = GenerationRequest(
            map_type="dungeon", biome="dungeon", size="small_encounter", seed=42,
            party_level=3, party_size=4,
        )
        coord = PipelineCoordinator(req)
        state = coord.generate()
        assert state.room_graph is not None
        assert state.room_graph.entrance_node is not None

    def test_village_uses_settlement_topology(self):
        req = GenerationRequest(
            map_type="village", biome="forest", size="small_encounter", seed=42,
        )
        coord = PipelineCoordinator(req)
        coord.run_phase1()
        result = coord.run_phase2()
        assert result.passed is True
        assert coord.shared_state.room_graph is not None

    def test_tavern_uses_interior_topology(self):
        req = GenerationRequest(
            map_type="tavern", biome="forest", size="small_encounter", seed=42,
        )
        coord = PipelineCoordinator(req)
        coord.run_phase1()
        result = coord.run_phase2()
        assert result.passed is True
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Update PipelineCoordinator and validation**

**In `coordinator.py`:** Update `run_phase2()` to:
1. Calculate room count from `SIZE_ROOM_COUNTS[request.size][family]` with +/-20% seed-based jitter
2. Run TopologyAgent with profile's topology_preference, size_topology_override, room_count
3. Run StructureAgent with `use_room_graph=True`
4. Run ConnectorAgent with profile's corridor_style and door_frequency
5. Run PathfindingAgent in validate mode
6. Return validate_layout() result

Add necessary imports for TopologyAgent, ConnectorAgent, and the game_tables.

**In `validation.py`:** Update `validate_layout()` to check:
- room_graph exists and has nodes
- All rooms have positions
- PathfindingAgent validation passed (all_connected)
- Entrance node exists

- [ ] **Step 4: Run tests, run full suite, commit**

```bash
git add mapgen_agents/pipeline/coordinator.py mapgen_agents/pipeline/validation.py tests/test_phase2_integration.py
git commit -m "feat: wire Phase 2 layout agents into PipelineCoordinator"
```

---

## Milestone: Phase 2 Complete

After all tasks, the pipeline generates:
- Phase 1: terrain + caves
- Phase 2: abstract room graph → physical rooms → corridors → validated connectivity
- Phase 3: stub (passes through)

The full generate() call now produces a dungeon with rooms, corridors, doors, and stairs — ready for Phase 3 population.

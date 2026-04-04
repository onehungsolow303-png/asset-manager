# Layered Renderer + Playtest Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the flat 2D map generator into a multi-layer z-level system with a pygame-based playtest viewer featuring d20 combat, fog of war, and parallax camera.

**Architecture:** SharedState wraps grid arrays in ZLevel objects keyed by z-index. Structure agent generates multi-floor buildings with stair transitions. A new spawn agent places player/enemy/NPC tokens. Renderer outputs per-layer PNGs + JSON. A pygame viewer loads this data for interactive exploration and turn-based combat.

**Tech Stack:** Python 3.13, numpy, Pillow, pygame 2.5+, existing agent pipeline

**Spec:** `docs/superpowers/specs/2026-04-04-layered-renderer-playtest-viewer-design.md`

---

## File Map

### Modified Files
| File | Responsibility | Changes |
|------|---------------|---------|
| `mapgen_agents/shared_state.py` | Central data layer | Add ZLevel, Transition, SpawnPoint dataclasses. Wrap ground arrays. Backwards-compat properties. |
| `mapgen_agents/orchestrator.py` | Agent dispatch | Register SpawnAgent |
| `mapgen_agents/planner.py` | DAG templates | Add spawn task to all templates |
| `mapgen_agents/agents/structure_agent.py` | Building placement | Multi-floor generation, stair transitions |
| `mapgen_agents/agents/asset_agent.py` | Asset scattering | Place on correct z-level |
| `mapgen_agents/agents/renderer_agent.py` | PNG output | Per-layer PNGs + flattened preview + JSON export |
| `mapgen_agents/gui.py` | Desktop GUI | Add Playtest button |
| `requirements.txt` | Dependencies | Add pygame |

### New Files
| File | Responsibility |
|------|---------------|
| `mapgen_agents/agents/spawn_agent.py` | Place player/enemy/NPC tokens with stat blocks |
| `mapgen_agents/viewer/__init__.py` | Viewer package init |
| `mapgen_agents/viewer/main.py` | Pygame entry point, game loop |
| `mapgen_agents/viewer/map_loader.py` | Load layered JSON + PNGs |
| `mapgen_agents/viewer/renderer.py` | Tile-based drawing, layer compositing, parallax |
| `mapgen_agents/viewer/camera.py` | Pan, zoom, follow, parallax offset |
| `mapgen_agents/viewer/fog_of_war.py` | Visibility states, LOS raycasting |
| `mapgen_agents/viewer/game_engine.py` | State machine: exploration/combat |
| `mapgen_agents/viewer/combat.py` | D20 rules, initiative, attacks, turn order |
| `mapgen_agents/viewer/entities.py` | Player, Enemy, NPC with stats and movement |
| `mapgen_agents/viewer/ai.py` | Enemy chase/patrol/guard behavior |
| `mapgen_agents/viewer/ui_overlay.py` | HUD, HP bars, combat log, minimap |
| `mapgen_agents/viewer/config.py` | Keybindings, tile size, constants |
| `tests/test_zlevel.py` | ZLevel data model tests |
| `tests/test_spawn_agent.py` | Spawn agent tests |
| `tests/test_combat.py` | D20 combat math tests |
| `tests/test_viewer_loader.py` | Map loader tests |

---

## Phase 1: Layer Data Model

### Task 1: ZLevel and Transition Data Classes

**Files:**
- Modify: `mapgen_agents/shared_state.py`
- Create: `tests/test_zlevel.py`

- [ ] **Step 1: Write failing tests for ZLevel**

Create `tests/test_zlevel.py`:

```python
"""Tests for the z-level data model."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mapgen_agents'))

import numpy as np
from shared_state import ZLevel, Transition, SpawnPoint, SharedState, MapConfig


def test_zlevel_creation():
    zl = ZLevel(z=0, width=64, height=64)
    assert zl.z == 0
    assert zl.terrain_color.shape == (64, 64, 3)
    assert zl.walkability.shape == (64, 64)
    assert zl.walkability.all()  # default walkable
    assert zl.structure_mask.shape == (64, 64)
    assert not zl.structure_mask.any()  # default no structures
    assert zl.entities == []
    assert zl.labels == []


def test_transition_creation():
    t = Transition(x=10, y=20, from_z=0, to_z=-1, transition_type="stairs_down")
    assert t.from_z == 0
    assert t.to_z == -1
    assert t.transition_type == "stairs_down"


def test_spawn_point_creation():
    sp = SpawnPoint(
        x=5, y=5, z=0, token_type="enemy", name="Goblin",
        stats={"HP": 10, "AC": 12, "STR": 14, "DEX": 10, "CON": 10, "SPD": 6, "ATK": "1d6+2"},
        ai_behavior="chase",
    )
    assert sp.token_type == "enemy"
    assert sp.stats["HP"] == 10


def test_shared_state_backwards_compat():
    """Existing agents use shared_state.terrain_color etc. Must still work."""
    cfg = MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42)
    ss = SharedState(cfg)

    # These must still work as before
    assert ss.terrain_color.shape == (64, 64, 3)
    assert ss.walkability.shape == (64, 64)
    assert ss.elevation.shape == (64, 64)
    assert ss.water_mask.shape == (64, 64)
    assert ss.structure_mask.shape == (64, 64)

    # Writing to them should write to ground level
    ss.terrain_color[0, 0] = [255, 0, 0]
    assert ss.ground.terrain_color[0, 0, 0] == 255


def test_shared_state_add_zlevel():
    cfg = MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42)
    ss = SharedState(cfg)

    basement = ss.add_zlevel(-1)
    assert basement.z == -1
    assert -1 in ss.levels
    assert ss.levels[-1] is basement

    roof = ss.add_zlevel(1)
    assert 1 in ss.levels
    assert ss.z_range == (-1, 1)


def test_shared_state_transitions():
    cfg = MapConfig(width=64, height=64, biome="dungeon", map_type="dungeon", seed=42)
    ss = SharedState(cfg)
    ss.add_zlevel(-1)

    ss.add_transition(Transition(x=10, y=10, from_z=0, to_z=-1, transition_type="stairs_down"))
    assert len(ss.transitions) == 1
    assert ss.transitions[0].to_z == -1


def test_shared_state_spawns():
    cfg = MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42)
    ss = SharedState(cfg)

    sp = SpawnPoint(x=32, y=32, z=0, token_type="player", name="Hero",
                    stats={"HP": 30, "AC": 15, "STR": 16, "DEX": 14, "CON": 14, "SPD": 6, "ATK": "1d8+3"},
                    ai_behavior="static")
    ss.spawns.append(sp)
    assert len(ss.spawns) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Dev/Map Generator" && .venv/Scripts/python.exe -m pytest tests/test_zlevel.py -v`
Expected: FAIL — ZLevel, Transition, SpawnPoint not defined; SharedState missing ground/levels/add_zlevel.

- [ ] **Step 3: Implement ZLevel, Transition, SpawnPoint and update SharedState**

Modify `mapgen_agents/shared_state.py`:

Add new dataclasses after the existing `Label` class:

```python
@dataclass
class ZLevel:
    """A single vertical layer of the map."""
    z: int
    width: int = 0
    height: int = 0
    terrain_color: np.ndarray = None
    walkability: np.ndarray = None
    structure_mask: np.ndarray = None
    water_mask: np.ndarray = None
    elevation: np.ndarray = None
    moisture: np.ndarray = None
    entities: list = field(default_factory=list)
    labels: list = field(default_factory=list)

    def __post_init__(self):
        h, w = self.height, self.width
        if h > 0 and w > 0:
            if self.terrain_color is None:
                self.terrain_color = np.zeros((h, w, 3), dtype=np.uint8)
            if self.walkability is None:
                self.walkability = np.ones((h, w), dtype=bool)
            if self.structure_mask is None:
                self.structure_mask = np.zeros((h, w), dtype=bool)
            if self.water_mask is None:
                self.water_mask = np.zeros((h, w), dtype=bool)
            if self.elevation is None:
                self.elevation = np.zeros((h, w), dtype=np.float32)
            if self.moisture is None:
                self.moisture = np.zeros((h, w), dtype=np.float32)


@dataclass
class Transition:
    """A link between two z-levels (stairs, ladder, trapdoor)."""
    x: int
    y: int
    from_z: int
    to_z: int
    transition_type: str  # "stairs_up", "stairs_down", "ladder", "trapdoor", "entrance"


@dataclass
class SpawnPoint:
    """A creature spawn location for the playtest viewer."""
    x: int
    y: int
    z: int
    token_type: str       # "player", "enemy", "npc"
    name: str
    stats: dict = field(default_factory=dict)
    ai_behavior: str = "static"  # "patrol", "guard", "chase", "static"
```

Rewrite `SharedState.__init__` to use ZLevel internally while keeping all existing attribute access working:

```python
class SharedState:
    def __init__(self, config: MapConfig):
        self.config = config
        self.rng = np.random.default_rng(config.seed)

        w, h = config.width, config.height

        # Ground level (z=0) — always exists
        self.ground = ZLevel(z=0, width=w, height=h)

        # All z-levels keyed by z-index
        self.levels: dict[int, ZLevel] = {0: self.ground}

        # Z-level connections and spawns
        self.transitions: list[Transition] = []
        self.spawns: list[SpawnPoint] = []

        # Entity lists (ground level shortcuts for backwards compat)
        self.paths: list[PathSegment] = []

        # Generation metadata
        self.metadata: dict[str, Any] = {
            "generation_seed": config.seed,
            "map_type": config.map_type,
            "created_at": time.time(),
            "agents_completed": [],
        }

    # --- Backwards-compat properties (all map to ground level) ---

    @property
    def elevation(self):
        return self.ground.elevation

    @elevation.setter
    def elevation(self, value):
        self.ground.elevation = value

    @property
    def moisture(self):
        return self.ground.moisture

    @moisture.setter
    def moisture(self, value):
        self.ground.moisture = value

    @property
    def walkability(self):
        return self.ground.walkability

    @walkability.setter
    def walkability(self, value):
        self.ground.walkability = value

    @property
    def water_mask(self):
        return self.ground.water_mask

    @water_mask.setter
    def water_mask(self, value):
        self.ground.water_mask = value

    @property
    def structure_mask(self):
        return self.ground.structure_mask

    @structure_mask.setter
    def structure_mask(self, value):
        self.ground.structure_mask = value

    @property
    def terrain_color(self):
        return self.ground.terrain_color

    @terrain_color.setter
    def terrain_color(self, value):
        self.ground.terrain_color = value

    @property
    def entities(self):
        return self.ground.entities

    @entities.setter
    def entities(self, value):
        self.ground.entities = value

    @property
    def labels(self):
        return self.ground.labels

    @labels.setter
    def labels(self, value):
        self.ground.labels = value

    # --- Z-level management ---

    def add_zlevel(self, z: int) -> ZLevel:
        """Create and register a new z-level. Returns the new ZLevel."""
        if z in self.levels:
            return self.levels[z]
        zl = ZLevel(z=z, width=self.config.width, height=self.config.height)
        self.levels[z] = zl
        return zl

    def add_transition(self, transition: Transition):
        self.transitions.append(transition)

    @property
    def z_range(self) -> tuple[int, int]:
        """Return (min_z, max_z) across all levels."""
        zs = list(self.levels.keys())
        return (min(zs), max(zs))

    # --- Existing methods (unchanged) ---

    def log_agent_completion(self, agent_name: str):
        self.metadata["agents_completed"].append({
            "agent": agent_name,
            "timestamp": time.time(),
        })

    def get_walkable_positions(self) -> np.ndarray:
        return self.ground.walkability & ~self.ground.water_mask & ~self.ground.structure_mask

    def summary(self) -> dict:
        total_entities = sum(len(zl.entities) for zl in self.levels.values())
        return {
            "map_size": f"{self.config.width}x{self.config.height}",
            "biome": self.config.biome,
            "map_type": self.config.map_type,
            "entities": total_entities,
            "paths": len(self.paths),
            "labels": sum(len(zl.labels) for zl in self.levels.values()),
            "z_levels": len(self.levels),
            "z_range": self.z_range,
            "transitions": len(self.transitions),
            "spawns": len(self.spawns),
            "agents_completed": [a["agent"] for a in self.metadata["agents_completed"]],
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "C:/Dev/Map Generator" && .venv/Scripts/python.exe -m pytest tests/test_zlevel.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Run existing test suite to confirm backwards compat**

Run: `cd "C:/Dev/Map Generator" && .venv/Scripts/python.exe mapgen_agents/test_all_types.py 2>&1 | tail -5`
Expected: 30/30 passed. No regressions.

- [ ] **Step 6: Commit**

```bash
cd "C:/Dev/Map Generator"
git add mapgen_agents/shared_state.py tests/test_zlevel.py
git commit -m "feat: add ZLevel, Transition, SpawnPoint data model with backwards compat"
```

---

## Phase 2: Spawn Agent + Structure Agent Multi-Floor

### Task 2: Spawn Agent

**Files:**
- Create: `mapgen_agents/agents/spawn_agent.py`
- Create: `tests/test_spawn_agent.py`
- Modify: `mapgen_agents/orchestrator.py`
- Modify: `mapgen_agents/planner.py`

- [ ] **Step 1: Write failing test for spawn agent**

Create `tests/test_spawn_agent.py`:

```python
"""Tests for the spawn agent."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mapgen_agents'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mapgen_agents', 'agents'))

import numpy as np
from shared_state import SharedState, MapConfig, SpawnPoint
from agents.spawn_agent import SpawnAgent


def test_spawn_agent_places_player():
    cfg = MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42)
    ss = SharedState(cfg)
    ss.ground.walkability[:] = True

    agent = SpawnAgent()
    result = agent.execute(ss, {"map_type": "village"})

    assert result["status"] == "completed"
    player_spawns = [s for s in ss.spawns if s.token_type == "player"]
    assert len(player_spawns) == 1
    assert player_spawns[0].stats["HP"] > 0


def test_spawn_agent_places_enemies():
    cfg = MapConfig(width=64, height=64, biome="dungeon", map_type="dungeon", seed=42)
    ss = SharedState(cfg)
    ss.ground.walkability[:] = True

    agent = SpawnAgent()
    result = agent.execute(ss, {"map_type": "dungeon"})

    enemies = [s for s in ss.spawns if s.token_type == "enemy"]
    assert len(enemies) > 0
    for e in enemies:
        assert "HP" in e.stats
        assert "AC" in e.stats
        assert "ATK" in e.stats


def test_spawn_agent_places_npcs_in_village():
    cfg = MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42)
    ss = SharedState(cfg)
    ss.ground.walkability[:] = True

    agent = SpawnAgent()
    agent.execute(ss, {"map_type": "village"})

    npcs = [s for s in ss.spawns if s.token_type == "npc"]
    assert len(npcs) > 0


def test_spawn_agent_respects_walkability():
    cfg = MapConfig(width=64, height=64, biome="forest", map_type="village", seed=42)
    ss = SharedState(cfg)
    ss.ground.walkability[:] = False  # nothing walkable
    ss.ground.walkability[32, 32] = True  # except one tile

    agent = SpawnAgent()
    agent.execute(ss, {"map_type": "village"})

    for sp in ss.spawns:
        assert ss.ground.walkability[sp.y, sp.x], f"Spawn at ({sp.x},{sp.y}) is on unwalkable tile"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Dev/Map Generator" && .venv/Scripts/python.exe -m pytest tests/test_spawn_agent.py -v`
Expected: FAIL — spawn_agent module not found.

- [ ] **Step 3: Implement SpawnAgent**

Create `mapgen_agents/agents/spawn_agent.py`:

```python
"""
SpawnAgent — Places player, enemy, and NPC spawn points with stat blocks.
Enemy difficulty scales by map type. All spawns placed on walkable tiles.
"""

import numpy as np
from base_agent import BaseAgent
from shared_state import SharedState, SpawnPoint
from typing import Any


# Player default stats
PLAYER_STATS = {
    "HP": 30, "AC": 15, "STR": 16, "DEX": 14, "CON": 14,
    "SPD": 6, "ATK": "1d8+3", "INT": 12, "WIS": 10, "CHA": 10,
}

# Enemy templates by challenge rating
ENEMY_TEMPLATES = {
    "rat": {"HP": 4, "AC": 10, "STR": 6, "DEX": 14, "CON": 8, "SPD": 6, "ATK": "1d4", "cr": 0.125},
    "wolf": {"HP": 11, "AC": 13, "STR": 12, "DEX": 15, "CON": 12, "SPD": 8, "ATK": "1d8+2", "cr": 0.25},
    "bandit": {"HP": 11, "AC": 12, "STR": 11, "DEX": 12, "CON": 12, "SPD": 6, "ATK": "1d6+1", "cr": 0.25},
    "skeleton": {"HP": 13, "AC": 13, "STR": 10, "DEX": 14, "CON": 10, "SPD": 6, "ATK": "1d6+2", "cr": 0.25},
    "goblin": {"HP": 7, "AC": 15, "STR": 8, "DEX": 14, "CON": 10, "SPD": 6, "ATK": "1d6+2", "cr": 0.25},
    "zombie": {"HP": 22, "AC": 8, "STR": 13, "DEX": 6, "CON": 16, "SPD": 4, "ATK": "1d6+1", "cr": 0.25},
    "guard": {"HP": 16, "AC": 16, "STR": 14, "DEX": 12, "CON": 14, "SPD": 6, "ATK": "1d8+2", "cr": 1},
    "orc": {"HP": 15, "AC": 13, "STR": 16, "DEX": 12, "CON": 16, "SPD": 6, "ATK": "1d12+3", "cr": 0.5},
    "ogre": {"HP": 59, "AC": 11, "STR": 19, "DEX": 8, "CON": 16, "SPD": 8, "ATK": "2d8+4", "cr": 2},
    "troll": {"HP": 84, "AC": 15, "STR": 18, "DEX": 13, "CON": 20, "SPD": 6, "ATK": "2d6+4", "cr": 5},
}

# NPC templates
NPC_TEMPLATES = [
    {"name": "Blacksmith", "ai_behavior": "static"},
    {"name": "Innkeeper", "ai_behavior": "static"},
    {"name": "Merchant", "ai_behavior": "static"},
    {"name": "Guard Captain", "ai_behavior": "patrol"},
    {"name": "Healer", "ai_behavior": "static"},
    {"name": "Farmer", "ai_behavior": "patrol"},
    {"name": "Bard", "ai_behavior": "patrol"},
    {"name": "Scholar", "ai_behavior": "static"},
]

# Map type -> enemy types and counts
MAP_ENEMIES = {
    "village": {"enemies": ["bandit", "wolf"], "count": (2, 5), "npcs": (3, 6)},
    "town": {"enemies": ["bandit", "rat"], "count": (3, 6), "npcs": (4, 8)},
    "city": {"enemies": ["bandit"], "count": (4, 8), "npcs": (6, 12)},
    "castle": {"enemies": ["guard", "orc"], "count": (6, 12), "npcs": (2, 5)},
    "fort": {"enemies": ["guard", "bandit"], "count": (5, 10), "npcs": (2, 4)},
    "tower": {"enemies": ["skeleton", "goblin"], "count": (3, 6), "npcs": (1, 2)},
    "dungeon": {"enemies": ["skeleton", "goblin", "orc"], "count": (8, 16), "npcs": (0, 1)},
    "cave": {"enemies": ["wolf", "goblin", "orc"], "count": (5, 10), "npcs": (0, 1)},
    "mine": {"enemies": ["goblin", "skeleton"], "count": (4, 8), "npcs": (0, 2)},
    "maze": {"enemies": ["skeleton", "zombie"], "count": (6, 12), "npcs": (0, 0)},
    "treasure_room": {"enemies": ["orc", "troll"], "count": (3, 6), "npcs": (0, 0)},
    "crypt": {"enemies": ["skeleton", "zombie"], "count": (6, 12), "npcs": (0, 0)},
    "tomb": {"enemies": ["skeleton", "zombie"], "count": (5, 10), "npcs": (0, 0)},
    "graveyard": {"enemies": ["skeleton", "zombie", "wolf"], "count": (4, 8), "npcs": (0, 1)},
    "temple": {"enemies": ["guard", "skeleton"], "count": (3, 6), "npcs": (2, 4)},
    "church": {"enemies": ["skeleton"], "count": (2, 4), "npcs": (1, 3)},
    "arena": {"enemies": ["orc", "ogre", "troll"], "count": (4, 8), "npcs": (0, 0)},
    "tavern": {"enemies": ["bandit"], "count": (1, 3), "npcs": (3, 6)},
    "prison": {"enemies": ["guard", "bandit"], "count": (4, 8), "npcs": (1, 3)},
    "library": {"enemies": ["skeleton"], "count": (2, 4), "npcs": (2, 4)},
    "throne_room": {"enemies": ["guard", "orc"], "count": (4, 8), "npcs": (2, 4)},
    "dock": {"enemies": ["bandit"], "count": (2, 5), "npcs": (3, 6)},
    "harbor": {"enemies": ["bandit"], "count": (3, 6), "npcs": (4, 8)},
    "factory": {"enemies": ["bandit", "rat"], "count": (3, 6), "npcs": (2, 4)},
    "shop": {"enemies": ["rat"], "count": (0, 2), "npcs": (1, 3)},
    "shopping_center": {"enemies": ["bandit", "rat"], "count": (2, 4), "npcs": (4, 8)},
    "wilderness": {"enemies": ["wolf", "bandit", "orc"], "count": (4, 8), "npcs": (0, 2)},
    "camp": {"enemies": ["bandit", "wolf"], "count": (2, 5), "npcs": (1, 3)},
    "outpost": {"enemies": ["orc", "goblin"], "count": (3, 6), "npcs": (1, 3)},
    "rest_area": {"enemies": ["wolf", "bandit"], "count": (1, 3), "npcs": (1, 3)},
    "crash_site": {"enemies": ["goblin", "orc"], "count": (3, 6), "npcs": (0, 1)},
}

# Fallback for unlisted types
DEFAULT_ENEMIES = {"enemies": ["bandit", "wolf"], "count": (2, 5), "npcs": (1, 3)}

NPC_STATS = {"HP": 10, "AC": 10, "STR": 10, "DEX": 10, "CON": 10, "SPD": 6, "ATK": "1d4"}


class SpawnAgent(BaseAgent):
    name = "SpawnAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        map_type = params.get("map_type", shared_state.config.map_type)
        rng = np.random.default_rng(shared_state.config.seed + 900)

        walkable = shared_state.get_walkable_positions()
        walkable_coords = np.argwhere(walkable)  # (N, 2) array of (y, x)

        if len(walkable_coords) == 0:
            return {"player_placed": False, "enemies_placed": 0, "npcs_placed": 0}

        def pick_walkable():
            idx = rng.integers(len(walkable_coords))
            y, x = walkable_coords[idx]
            return int(x), int(y)

        # 1. Place player at map center area
        cx, cy = shared_state.config.width // 2, shared_state.config.height // 2
        best_dist = float("inf")
        px, py = pick_walkable()
        for _ in range(50):
            tx, ty = pick_walkable()
            d = abs(tx - cx) + abs(ty - cy)
            if d < best_dist:
                best_dist = d
                px, py = tx, ty

        shared_state.spawns.append(SpawnPoint(
            x=px, y=py, z=0, token_type="player", name="Hero",
            stats=dict(PLAYER_STATS), ai_behavior="static",
        ))

        # 2. Place enemies
        enemy_cfg = MAP_ENEMIES.get(map_type, DEFAULT_ENEMIES)
        lo, hi = enemy_cfg["count"]
        enemy_count = rng.integers(lo, hi + 1)
        enemy_types = enemy_cfg["enemies"]
        enemies_placed = 0

        for _ in range(enemy_count):
            etype = enemy_types[rng.integers(len(enemy_types))]
            template = ENEMY_TEMPLATES.get(etype, ENEMY_TEMPLATES["bandit"])
            ex, ey = pick_walkable()
            # Don't spawn on top of player
            if abs(ex - px) < 8 and abs(ey - py) < 8:
                continue
            stats = {k: v for k, v in template.items() if k != "cr"}
            shared_state.spawns.append(SpawnPoint(
                x=ex, y=ey, z=0, token_type="enemy",
                name=etype.replace("_", " ").title(),
                stats=stats, ai_behavior="chase",
            ))
            enemies_placed += 1

        # 3. Place NPCs
        npc_lo, npc_hi = enemy_cfg["npcs"]
        npc_count = rng.integers(npc_lo, npc_hi + 1) if npc_hi > 0 else 0
        npcs_placed = 0

        available_npcs = list(NPC_TEMPLATES)
        rng.shuffle(available_npcs)

        for i in range(min(npc_count, len(available_npcs))):
            nx, ny = pick_walkable()
            npc = available_npcs[i]
            shared_state.spawns.append(SpawnPoint(
                x=nx, y=ny, z=0, token_type="npc",
                name=npc["name"], stats=dict(NPC_STATS),
                ai_behavior=npc["ai_behavior"],
            ))
            npcs_placed += 1

        return {
            "player_placed": True,
            "enemies_placed": enemies_placed,
            "npcs_placed": npcs_placed,
            "total_spawns": len(shared_state.spawns),
        }
```

- [ ] **Step 4: Run spawn agent tests**

Run: `cd "C:/Dev/Map Generator" && .venv/Scripts/python.exe -m pytest tests/test_spawn_agent.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Register SpawnAgent in orchestrator**

Add to `mapgen_agents/orchestrator.py` imports:

```python
from agents.spawn_agent import SpawnAgent
```

Add to `AGENT_REGISTRY`:

```python
"SpawnAgent": SpawnAgent,
```

- [ ] **Step 6: Add spawn task to DAG templates in planner.py**

In `mapgen_agents/planner.py`, for each DAG template, add a spawn task node after structures/rooms but before render. The spawn node depends on the structure task and goes into the same level as labeling. Example for the village template:

```python
TaskNode("spawns", "SpawnAgent", {"map_type": "{map_type}"}, ["buildings"]),
```

Add `"spawns"` to the render node's dependencies alongside `"labeling"`.

Apply this pattern to all 35 DAG templates — spawn depends on the structure/building task, render depends on spawn.

- [ ] **Step 7: Run full test suite**

Run: `cd "C:/Dev/Map Generator" && .venv/Scripts/python.exe mapgen_agents/test_all_types.py 2>&1 | tail -5`
Expected: 30/30 passed with spawn agent now in the pipeline.

- [ ] **Step 8: Commit**

```bash
cd "C:/Dev/Map Generator"
git add mapgen_agents/agents/spawn_agent.py tests/test_spawn_agent.py mapgen_agents/orchestrator.py mapgen_agents/planner.py
git commit -m "feat: add SpawnAgent for player/enemy/NPC placement with d20 stat blocks"
```

---

### Task 3: Structure Agent Multi-Floor Generation

**Files:**
- Modify: `mapgen_agents/agents/structure_agent.py`

This is the largest change. The structure agent must create additional z-levels for multi-floor buildings and place stair transitions between them.

- [ ] **Step 1: Add `_generate_floors` method to StructureAgent**

Add a method that, after a building is placed on z=0, creates upper/lower z-levels:

```python
def _generate_floors(self, shared_state, x, y, w, h, structure_type, rng):
    """Generate additional z-levels for a building based on its type."""
    floor_configs = {
        "village": [(1, "roof")],
        "town": [(1, "roof")],
        "city": [(1, "upper"), (2, "roof")],
        "castle": [(-1, "dungeon"), (-2, "vault"), (1, "upper_hall"), (2, "battlements")],
        "fort": [(1, "upper"), (2, "roof")],
        "tower": [(1, "floor2"), (2, "floor3"), (3, "top")],
        "dungeon": [(-1, "level1"), (-2, "level2")],
        "cave": [(-1, "depths")],
        "mine": [(-1, "shaft1"), (-2, "shaft2")],
        "temple": [(-1, "crypt"), (1, "belfry")],
        "church": [(-1, "crypt"), (1, "belfry")],
        "tavern": [(1, "rooms")],
        "prison": [(-1, "cells")],
        "library": [(1, "upper_stacks")],
        "throne_room": [(1, "gallery")],
        "crypt": [(-1, "deep_crypt"), (-2, "ossuary")],
        "tomb": [(-1, "burial_chamber"), (-2, "sealed_vault")],
    }

    floors = floor_configs.get(structure_type, [(1, "roof")])

    for z_offset, floor_name in floors:
        zl = shared_state.add_zlevel(z_offset)

        # Fill building footprint on this level
        y1, y2 = max(0, y), min(shared_state.config.height, y + h)
        x1, x2 = max(0, x), min(shared_state.config.width, x + w)

        if z_offset > 0:
            # Upper floor / roof: stone or wood floor color
            color = (140, 120, 80) if "roof" in floor_name else (160, 140, 110)
        else:
            # Basement / underground: dark stone
            color = (80, 75, 65)

        zl.terrain_color[y1:y2, x1:x2] = color
        zl.structure_mask[y1:y2, x1:x2] = True
        # Walls around edges
        zl.walkability[y1:y2, x1:x2] = True
        zl.walkability[y1, x1:x2] = False  # top wall
        zl.walkability[y2-1, x1:x2] = False  # bottom wall
        zl.walkability[y1:y2, x1] = False  # left wall
        zl.walkability[y1:y2, x2-1] = False  # right wall

        # Place stairs connecting to the previous level
        stair_x = x + w // 2
        stair_y = y + h // 2
        prev_z = z_offset - 1 if z_offset > 0 else z_offset + 1
        t_type = "stairs_up" if z_offset > 0 else "stairs_down"

        shared_state.add_transition(Transition(
            x=stair_x, y=stair_y,
            from_z=prev_z, to_z=z_offset,
            transition_type=t_type,
        ))
```

- [ ] **Step 2: Call `_generate_floors` from `_place_buildings` after each building**

In the `_place_buildings` method (and other generator methods like `_generate_dungeon_rooms`, `_generate_castle`, etc.), add a call to `_generate_floors` after each building is placed:

```python
self._generate_floors(shared_state, bx, by, bw, bh, structure_type, rng)
```

Start with `_place_buildings` only (covers village, town, city, shop, outpost, camp, rest_area, fort). Other generators can be enhanced incrementally.

- [ ] **Step 3: Run full test suite to verify no regressions**

Run: `cd "C:/Dev/Map Generator" && .venv/Scripts/python.exe mapgen_agents/test_all_types.py 2>&1 | tail -5`
Expected: 30/30 passed. Buildings now generate z-levels.

- [ ] **Step 4: Verify z-levels are being created**

```python
import sys; sys.path.insert(0, 'mapgen_agents')
from map_generator import MapGenerator
gen = MapGenerator(verbose=False)
result = gen.generate(goal='test', map_type='castle', biome='forest', size='small_encounter', seed=42)
ss = result['shared_state']
print(f"Z-levels: {sorted(ss.levels.keys())}")
print(f"Transitions: {len(ss.transitions)}")
print(f"Spawns: {len(ss.spawns)}")
```
Expected: Multiple z-levels, transitions > 0, spawns > 0.

- [ ] **Step 5: Commit**

```bash
git add mapgen_agents/agents/structure_agent.py
git commit -m "feat: multi-floor building generation with stair transitions"
```

---

## Phase 3: Layered Renderer + JSON Export

### Task 4: Per-Layer PNG Output and JSON Map Data

**Files:**
- Modify: `mapgen_agents/agents/renderer_agent.py`

- [ ] **Step 1: Add `_export_layered_data` method to RendererAgent**

After the existing render logic that produces the flattened preview, add a method that:
1. Renders each z-level as a separate PNG (using the same compositing logic but per-level)
2. Exports `map_data.json` containing all level data, transitions, spawns, labels
3. Serializes walkability as run-length-encoded arrays (compact)

```python
def _export_layered_data(self, shared_state, output_dir):
    """Export per-layer PNGs and a JSON manifest for the viewer."""
    import json

    os.makedirs(output_dir, exist_ok=True)
    z_level_data = []

    for z, zl in sorted(shared_state.levels.items()):
        # Save terrain PNG for this level
        fname = f"z_{z}.png" if z >= 0 else f"z_neg{abs(z)}.png"
        fpath = os.path.join(output_dir, fname)
        img = Image.fromarray(zl.terrain_color, "RGB")
        img.save(fpath)

        # Serialize walkability as flat list of 0/1
        walk_flat = zl.walkability.astype(np.uint8).flatten().tolist()

        # Serialize entities
        entities_data = []
        for e in zl.entities:
            entities_data.append({
                "type": e.entity_type, "x": e.position[0], "y": e.position[1],
                "w": e.size[0], "h": e.size[1], "variant": e.variant,
                "metadata": e.metadata,
            })

        z_level_data.append({
            "z": z,
            "terrain_png": fname,
            "walkability": walk_flat,
            "entities": entities_data,
        })

    # Transitions
    transitions_data = [
        {"x": t.x, "y": t.y, "from_z": t.from_z, "to_z": t.to_z, "type": t.transition_type}
        for t in shared_state.transitions
    ]

    # Spawns
    spawns_data = [
        {"x": s.x, "y": s.y, "z": s.z, "token_type": s.token_type,
         "name": s.name, "stats": s.stats, "ai_behavior": s.ai_behavior}
        for s in shared_state.spawns
    ]

    # Labels across all levels
    labels_data = []
    for z, zl in shared_state.levels.items():
        for lb in zl.labels:
            labels_data.append({
                "x": lb.position[0], "y": lb.position[1], "z": z,
                "text": lb.text, "category": lb.category,
            })

    map_data = {
        "config": {
            "width": shared_state.config.width,
            "height": shared_state.config.height,
            "biome": shared_state.config.biome,
            "map_type": shared_state.config.map_type,
            "seed": shared_state.config.seed,
        },
        "z_levels": z_level_data,
        "transitions": transitions_data,
        "spawns": spawns_data,
        "labels": labels_data,
    }

    json_path = os.path.join(output_dir, "map_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(map_data, f)

    return json_path
```

- [ ] **Step 2: Call `_export_layered_data` at end of `_run`**

Add after the save step, before the return:

```python
# Export layered data for viewer
map_output_dir = os.path.dirname(output_path) or "."
json_path = self._export_layered_data(shared_state, map_output_dir)
```

Add `"map_data_json": json_path` to the return dict.

- [ ] **Step 3: Test that map_data.json is generated**

```bash
cd "C:/Dev/Map Generator"
.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, 'mapgen_agents')
from map_generator import MapGenerator
import json
gen = MapGenerator(verbose=False)
result = gen.generate(goal='test', map_type='village', biome='forest', size='small_encounter', seed=42)
with open('./output/map_data.json') as f:
    data = json.load(f)
print(f'Z-levels: {len(data[\"z_levels\"])}')
print(f'Transitions: {len(data[\"transitions\"])}')
print(f'Spawns: {len(data[\"spawns\"])}')
print(f'Config: {data[\"config\"][\"map_type\"]}')
"
```
Expected: Z-levels >= 1, spawns > 0, valid JSON structure.

- [ ] **Step 4: Run full test suite**

Run: `cd "C:/Dev/Map Generator" && .venv/Scripts/python.exe mapgen_agents/test_all_types.py 2>&1 | tail -5`
Expected: 30/30 passed.

- [ ] **Step 5: Commit**

```bash
git add mapgen_agents/agents/renderer_agent.py
git commit -m "feat: export per-layer PNGs and map_data.json for viewer"
```

---

## Phase 4: Pygame Viewer Core

### Task 5: Viewer Config and Entities

**Files:**
- Create: `mapgen_agents/viewer/__init__.py`
- Create: `mapgen_agents/viewer/config.py`
- Create: `mapgen_agents/viewer/entities.py`
- Create: `tests/test_combat.py`

- [ ] **Step 1: Create viewer package and config**

Create `mapgen_agents/viewer/__init__.py` (empty file).

Create `mapgen_agents/viewer/config.py`:

```python
"""Viewer configuration, constants, and keybindings."""

import pygame

# Display
WINDOW_TITLE = "Map Generator - Playtest Viewer"
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 900
FPS = 60
TILE_SIZE = 16  # pixels per tile

# Colors (R, G, B)
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_PLAYER = (59, 130, 246)       # Blue
COLOR_PLAYER_BORDER = (96, 165, 250)
COLOR_ENEMY = (239, 68, 68)         # Red
COLOR_ENEMY_BORDER = (248, 113, 113)
COLOR_NPC = (212, 160, 60)          # Gold
COLOR_NPC_BORDER = (240, 192, 96)
COLOR_FOG_UNEXPLORED = (0, 0, 0)
COLOR_FOG_EXPLORED = (0, 0, 0, 128)  # 50% black
COLOR_HP_GREEN = (34, 197, 94)
COLOR_HP_RED = (239, 68, 68)
COLOR_HP_BG = (30, 30, 30)
COLOR_UI_BG = (26, 26, 46, 220)
COLOR_UI_TEXT = (234, 234, 234)
COLOR_UI_GOLD = (212, 160, 60)
COLOR_GRID = (255, 255, 255, 40)
COLOR_TRANSITION = (180, 130, 255)  # Purple for stairs

# Parallax
PARALLAX_STRENGTH = 0.05  # 5% of tile size per z-level

# Fog of war
FOW_SIGHT_RADIUS = 12  # tiles

# Combat
COMBAT_DETECT_RANGE = 12  # tiles
MOVEMENT_PER_TURN = 6     # tiles (30ft in 5ft squares)

# Keybindings
KEY_MOVE_UP = [pygame.K_w, pygame.K_UP]
KEY_MOVE_DOWN = [pygame.K_s, pygame.K_DOWN]
KEY_MOVE_LEFT = [pygame.K_a, pygame.K_LEFT]
KEY_MOVE_RIGHT = [pygame.K_d, pygame.K_RIGHT]
KEY_INTERACT = pygame.K_f
KEY_END_TURN = pygame.K_SPACE
KEY_TOGGLE_PERSPECTIVE = pygame.K_TAB
KEY_ZLEVEL_UP = pygame.K_RIGHTBRACKET
KEY_ZLEVEL_DOWN = pygame.K_LEFTBRACKET
KEY_TOGGLE_GRID = pygame.K_g
KEY_TOGGLE_FOG = pygame.K_v
KEY_QUIT = pygame.K_ESCAPE

# Token rendering
TOKEN_RADIUS = 6  # pixels
TOKEN_BORDER = 2
```

- [ ] **Step 2: Create entities module**

Create `mapgen_agents/viewer/entities.py`:

```python
"""Game entities: Player, Enemy, NPC with d20 stat blocks."""

import random
from dataclasses import dataclass, field


def roll_dice(dice_str: str) -> int:
    """Parse and roll dice notation like '1d8+3', '2d6', '1d4'."""
    dice_str = dice_str.strip()
    bonus = 0
    if "+" in dice_str:
        parts = dice_str.split("+")
        dice_str = parts[0]
        bonus = int(parts[1])
    elif "-" in dice_str:
        parts = dice_str.split("-")
        dice_str = parts[0]
        bonus = -int(parts[1])

    num, sides = dice_str.split("d")
    num = int(num)
    sides = int(sides)

    total = sum(random.randint(1, sides) for _ in range(num))
    return total + bonus


def ability_modifier(score: int) -> int:
    """D20 ability modifier: (score - 10) // 2"""
    return (score - 10) // 2


@dataclass
class Creature:
    """Base creature with d20 stats."""
    name: str
    x: int
    y: int
    z: int
    token_type: str  # "player", "enemy", "npc"
    ai_behavior: str = "static"

    # Stats
    hp: int = 10
    max_hp: int = 10
    ac: int = 10
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    speed: int = 6
    atk_dice: str = "1d4"
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

    # State
    alive: bool = True
    movement_remaining: int = 0
    has_action: bool = True
    visible: bool = False

    @classmethod
    def from_spawn(cls, spawn_data: dict) -> "Creature":
        stats = spawn_data.get("stats", {})
        hp = stats.get("HP", 10)
        return cls(
            name=spawn_data["name"],
            x=spawn_data["x"],
            y=spawn_data["y"],
            z=spawn_data["z"],
            token_type=spawn_data["token_type"],
            ai_behavior=spawn_data.get("ai_behavior", "static"),
            hp=hp,
            max_hp=hp,
            ac=stats.get("AC", 10),
            strength=stats.get("STR", 10),
            dexterity=stats.get("DEX", 10),
            constitution=stats.get("CON", 10),
            speed=stats.get("SPD", 6),
            atk_dice=stats.get("ATK", "1d4"),
            intelligence=stats.get("INT", 10),
            wisdom=stats.get("WIS", 10),
            charisma=stats.get("CHA", 10),
        )

    def roll_initiative(self) -> int:
        return roll_dice("1d20") + ability_modifier(self.dexterity)

    def roll_attack(self) -> int:
        mod = ability_modifier(self.strength)
        return roll_dice("1d20") + mod

    def roll_damage(self) -> int:
        return max(1, roll_dice(self.atk_dice))

    def take_damage(self, amount: int):
        self.hp = max(0, self.hp - amount)
        if self.hp == 0:
            self.alive = False

    def start_turn(self):
        self.movement_remaining = self.speed
        self.has_action = True

    @property
    def hp_pct(self) -> float:
        return self.hp / self.max_hp if self.max_hp > 0 else 0
```

- [ ] **Step 3: Write combat math tests**

Create `tests/test_combat.py`:

```python
"""Tests for d20 combat math."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mapgen_agents', 'viewer'))

from entities import roll_dice, ability_modifier, Creature


def test_ability_modifier():
    assert ability_modifier(10) == 0
    assert ability_modifier(16) == 3
    assert ability_modifier(8) == -1
    assert ability_modifier(20) == 5
    assert ability_modifier(1) == -5


def test_roll_dice_simple():
    for _ in range(100):
        result = roll_dice("1d6")
        assert 1 <= result <= 6


def test_roll_dice_with_bonus():
    for _ in range(100):
        result = roll_dice("1d6+3")
        assert 4 <= result <= 9


def test_roll_dice_multi():
    for _ in range(100):
        result = roll_dice("2d6")
        assert 2 <= result <= 12


def test_creature_from_spawn():
    spawn = {
        "x": 10, "y": 20, "z": 0,
        "token_type": "enemy", "name": "Goblin",
        "stats": {"HP": 7, "AC": 15, "STR": 8, "DEX": 14, "CON": 10, "SPD": 6, "ATK": "1d6+2"},
        "ai_behavior": "chase",
    }
    c = Creature.from_spawn(spawn)
    assert c.hp == 7
    assert c.max_hp == 7
    assert c.ac == 15
    assert c.atk_dice == "1d6+2"
    assert c.alive


def test_creature_take_damage():
    c = Creature(name="Test", x=0, y=0, z=0, token_type="enemy", hp=10, max_hp=10)
    c.take_damage(3)
    assert c.hp == 7
    assert c.alive
    c.take_damage(7)
    assert c.hp == 0
    assert not c.alive


def test_creature_start_turn():
    c = Creature(name="Test", x=0, y=0, z=0, token_type="player", speed=6)
    c.start_turn()
    assert c.movement_remaining == 6
    assert c.has_action
```

- [ ] **Step 4: Run combat tests**

Run: `cd "C:/Dev/Map Generator" && .venv/Scripts/python.exe -m pytest tests/test_combat.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mapgen_agents/viewer/ tests/test_combat.py
git commit -m "feat: add viewer config, entity system, d20 combat math"
```

---

### Task 6: Map Loader

**Files:**
- Create: `mapgen_agents/viewer/map_loader.py`
- Create: `tests/test_viewer_loader.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_viewer_loader.py`:

```python
"""Tests for the viewer map loader."""
import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mapgen_agents', 'viewer'))

import numpy as np
from PIL import Image
from map_loader import load_map


def _make_test_map(tmp_dir):
    """Create a minimal map_data.json + z_0.png for testing."""
    w, h = 32, 32
    img = Image.fromarray(np.full((h, w, 3), 100, dtype=np.uint8), "RGB")
    img.save(os.path.join(tmp_dir, "z_0.png"))

    data = {
        "config": {"width": w, "height": h, "biome": "forest", "map_type": "village", "seed": 42},
        "z_levels": [
            {"z": 0, "terrain_png": "z_0.png",
             "walkability": [1] * (w * h), "entities": []},
        ],
        "transitions": [{"x": 16, "y": 16, "from_z": 0, "to_z": -1, "type": "stairs_down"}],
        "spawns": [
            {"x": 5, "y": 5, "z": 0, "token_type": "player", "name": "Hero",
             "stats": {"HP": 30, "AC": 15, "STR": 16, "DEX": 14, "CON": 14, "SPD": 6, "ATK": "1d8+3"},
             "ai_behavior": "static"},
        ],
        "labels": [],
    }

    json_path = os.path.join(tmp_dir, "map_data.json")
    with open(json_path, "w") as f:
        json.dump(data, f)

    return json_path


def test_load_map_basic():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_test_map(tmp)
        game_map = load_map(os.path.dirname(path))

        assert game_map.width == 32
        assert game_map.height == 32
        assert game_map.config["biome"] == "forest"
        assert 0 in game_map.terrain_surfaces
        assert len(game_map.transitions) == 1
        assert len(game_map.spawns) == 1
        assert game_map.spawns[0]["token_type"] == "player"


def test_load_map_walkability():
    with tempfile.TemporaryDirectory() as tmp:
        path = _make_test_map(tmp)
        game_map = load_map(os.path.dirname(path))

        assert game_map.walkability[0][0, 0] == True
        assert game_map.walkability[0].shape == (32, 32)
```

- [ ] **Step 2: Implement map_loader**

Create `mapgen_agents/viewer/map_loader.py`:

```python
"""Load layered map data from JSON + PNGs for the pygame viewer."""

import json
import os
import numpy as np
from dataclasses import dataclass, field
from PIL import Image


@dataclass
class GameMap:
    """Loaded map data ready for the viewer."""
    width: int
    height: int
    config: dict
    terrain_images: dict = field(default_factory=dict)    # z -> PIL.Image
    terrain_surfaces: dict = field(default_factory=dict)  # z -> pygame Surface (set later)
    walkability: dict = field(default_factory=dict)        # z -> np.bool array
    entities: dict = field(default_factory=dict)           # z -> list of entity dicts
    transitions: list = field(default_factory=list)
    spawns: list = field(default_factory=list)
    labels: list = field(default_factory=list)

    @property
    def z_levels(self) -> list[int]:
        return sorted(self.terrain_images.keys())


def load_map(map_dir: str) -> GameMap:
    """Load a map from a directory containing map_data.json and z_*.png files."""
    json_path = os.path.join(map_dir, "map_data.json")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cfg = data["config"]
    w, h = cfg["width"], cfg["height"]

    game_map = GameMap(width=w, height=h, config=cfg)

    # Load z-level data
    for zl_data in data.get("z_levels", []):
        z = zl_data["z"]
        png_path = os.path.join(map_dir, zl_data["terrain_png"])

        if os.path.exists(png_path):
            game_map.terrain_images[z] = Image.open(png_path).convert("RGB")

        # Reconstruct walkability array
        walk_flat = zl_data.get("walkability", [])
        if walk_flat:
            walk_arr = np.array(walk_flat, dtype=bool).reshape((h, w))
        else:
            walk_arr = np.ones((h, w), dtype=bool)
        game_map.walkability[z] = walk_arr

        # Store entities per level
        game_map.entities[z] = zl_data.get("entities", [])

    game_map.transitions = data.get("transitions", [])
    game_map.spawns = data.get("spawns", [])
    game_map.labels = data.get("labels", [])

    # Mark terrain_surfaces keys (actual pygame Surfaces created by renderer)
    for z in game_map.terrain_images:
        game_map.terrain_surfaces[z] = None  # populated by renderer at init

    return game_map
```

- [ ] **Step 3: Run loader tests**

Run: `cd "C:/Dev/Map Generator" && .venv/Scripts/python.exe -m pytest tests/test_viewer_loader.py -v`
Expected: All 2 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add mapgen_agents/viewer/map_loader.py tests/test_viewer_loader.py
git commit -m "feat: add map loader for viewer (JSON + PNG parsing)"
```

---

### Task 7: Camera, Fog of War, Renderer, AI, Combat Engine, UI Overlay, Main Loop

**Files:**
- Create: `mapgen_agents/viewer/camera.py`
- Create: `mapgen_agents/viewer/fog_of_war.py`
- Create: `mapgen_agents/viewer/renderer.py`
- Create: `mapgen_agents/viewer/ai.py`
- Create: `mapgen_agents/viewer/combat.py`
- Create: `mapgen_agents/viewer/game_engine.py`
- Create: `mapgen_agents/viewer/ui_overlay.py`
- Create: `mapgen_agents/viewer/main.py`
- Modify: `requirements.txt`

This is the core viewer. Each file is a self-contained module. Implement them sequentially since they reference each other.

- [ ] **Step 1: Install pygame**

```bash
cd "C:/Dev/Map Generator" && .venv/Scripts/python.exe -m pip install pygame
```

Add `pygame>=2.5.0` to `requirements.txt`.

- [ ] **Step 2: Create camera.py**

```python
"""Camera with pan, zoom, smooth follow, and parallax offset."""

from config import TILE_SIZE, PARALLAX_STRENGTH, WINDOW_WIDTH, WINDOW_HEIGHT


class Camera:
    def __init__(self, map_width, map_height):
        self.x = 0.0  # world position (pixels)
        self.y = 0.0
        self.zoom = 1.0
        self.min_zoom = 0.25
        self.max_zoom = 4.0
        self.map_width = map_width * TILE_SIZE
        self.map_height = map_height * TILE_SIZE
        self.perspective_mode = False
        self.angle_x = 0.0  # -1 to 1
        self.angle_y = 0.0

        # Smooth follow
        self.target_x = 0.0
        self.target_y = 0.0
        self.follow_speed = 0.1

    def follow(self, world_x, world_y):
        self.target_x = world_x - WINDOW_WIDTH / (2 * self.zoom)
        self.target_y = world_y - WINDOW_HEIGHT / (2 * self.zoom)

    def update(self):
        self.x += (self.target_x - self.x) * self.follow_speed
        self.y += (self.target_y - self.y) * self.follow_speed

    def zoom_in(self):
        self.zoom = min(self.max_zoom, self.zoom * 1.15)

    def zoom_out(self):
        self.zoom = max(self.min_zoom, self.zoom / 1.15)

    def pan(self, dx, dy):
        self.x += dx / self.zoom
        self.y += dy / self.zoom
        self.target_x = self.x
        self.target_y = self.y

    def world_to_screen(self, wx, wy, z_offset=0):
        parallax = 0
        if self.perspective_mode:
            parallax = z_offset * PARALLAX_STRENGTH * TILE_SIZE
        sx = (wx - self.x + parallax * self.angle_x) * self.zoom
        sy = (wy - self.y + parallax * self.angle_y) * self.zoom
        return int(sx), int(sy)

    def screen_to_world(self, sx, sy):
        wx = sx / self.zoom + self.x
        wy = sy / self.zoom + self.y
        return wx, wy

    def visible_tile_range(self):
        x1 = max(0, int(self.x / TILE_SIZE))
        y1 = max(0, int(self.y / TILE_SIZE))
        x2 = min(self.map_width // TILE_SIZE, int((self.x + WINDOW_WIDTH / self.zoom) / TILE_SIZE) + 1)
        y2 = min(self.map_height // TILE_SIZE, int((self.y + WINDOW_HEIGHT / self.zoom) / TILE_SIZE) + 1)
        return x1, y1, x2, y2

    def toggle_perspective(self):
        self.perspective_mode = not self.perspective_mode
        if not self.perspective_mode:
            self.angle_x = 0
            self.angle_y = 0
```

- [ ] **Step 3: Create fog_of_war.py**

```python
"""Three-state fog of war with line-of-sight raycasting."""

import numpy as np
from config import FOW_SIGHT_RADIUS

# States: 0 = unexplored, 1 = explored (dim), 2 = visible (clear)
UNEXPLORED = 0
EXPLORED = 1
VISIBLE = 2


class FogOfWar:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.enabled = True
        # Per z-level fog state
        self.state: dict[int, np.ndarray] = {}

    def get_or_create(self, z: int) -> np.ndarray:
        if z not in self.state:
            self.state[z] = np.zeros((self.height, self.width), dtype=np.uint8)
        return self.state[z]

    def update(self, player_x, player_y, player_z, walkability):
        if not self.enabled:
            return

        fog = self.get_or_create(player_z)

        # Dim previously visible tiles to explored
        fog[fog == VISIBLE] = EXPLORED

        # Raycasting from player position
        px, py = int(player_x), int(player_y)
        walk = walkability.get(player_z)
        if walk is None:
            return

        # Cast rays in a circle
        for angle_step in range(360):
            import math
            angle = math.radians(angle_step)
            dx = math.cos(angle)
            dy = math.sin(angle)

            rx, ry = float(px), float(py)
            for _ in range(FOW_SIGHT_RADIUS):
                ix, iy = int(round(rx)), int(round(ry))
                if not (0 <= ix < self.width and 0 <= iy < self.height):
                    break
                fog[iy, ix] = VISIBLE
                if not walk[iy, ix]:
                    break  # wall blocks LOS
                rx += dx
                ry += dy

    def toggle(self):
        self.enabled = not self.enabled
```

- [ ] **Step 4: Create ai.py**

```python
"""Enemy AI behaviors: chase, patrol, guard."""

import math


def manhattan_dist(x1, y1, x2, y2):
    return abs(x1 - x2) + abs(y1 - y2)


def move_toward(creature, target_x, target_y, walkability, creatures, max_steps=None):
    """Move creature toward target, one tile at a time. Returns tiles moved."""
    if max_steps is None:
        max_steps = creature.movement_remaining

    moved = 0
    h, w = walkability.shape

    for _ in range(max_steps):
        if creature.x == target_x and creature.y == target_y:
            break

        # Pick best adjacent tile
        best_dist = manhattan_dist(creature.x, creature.y, target_x, target_y)
        best_move = None

        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = creature.x + dx, creature.y + dy
            if not (0 <= nx < w and 0 <= ny < h):
                continue
            if not walkability[ny, nx]:
                continue
            # Don't walk onto other creatures
            occupied = any(c.x == nx and c.y == ny and c.alive and c is not creature
                          for c in creatures)
            if occupied:
                continue

            dist = manhattan_dist(nx, ny, target_x, target_y)
            if dist < best_dist:
                best_dist = dist
                best_move = (nx, ny)

        if best_move is None:
            break

        creature.x, creature.y = best_move
        creature.movement_remaining -= 1
        moved += 1

        if creature.movement_remaining <= 0:
            break

    return moved


def ai_turn(creature, player, walkability, all_creatures):
    """Execute one AI turn for an enemy creature."""
    creature.start_turn()

    if not creature.alive or creature.token_type != "enemy":
        return []

    log = []

    if creature.ai_behavior == "static":
        return log

    # Chase: move toward player
    dist = manhattan_dist(creature.x, creature.y, player.x, player.y)

    if dist <= 1:
        # Adjacent: attack
        if creature.has_action:
            attack_roll = creature.roll_attack()
            if attack_roll >= player.ac:
                damage = creature.roll_damage()
                player.take_damage(damage)
                log.append(f"{creature.name} hits {player.name} for {damage} damage! (roll: {attack_roll} vs AC {player.ac})")
            else:
                log.append(f"{creature.name} misses {player.name}. (roll: {attack_roll} vs AC {player.ac})")
            creature.has_action = False
    else:
        # Move toward player
        moved = move_toward(creature, player.x, player.y, walkability, all_creatures)
        if moved > 0:
            log.append(f"{creature.name} moves {moved} tiles toward {player.name}.")

        # Check if now adjacent and can attack
        if manhattan_dist(creature.x, creature.y, player.x, player.y) <= 1 and creature.has_action:
            attack_roll = creature.roll_attack()
            if attack_roll >= player.ac:
                damage = creature.roll_damage()
                player.take_damage(damage)
                log.append(f"{creature.name} hits {player.name} for {damage}! (roll: {attack_roll} vs AC {player.ac})")
            else:
                log.append(f"{creature.name} misses {player.name}. (roll: {attack_roll} vs AC {player.ac})")
            creature.has_action = False

    return log
```

- [ ] **Step 5: Create combat.py**

```python
"""D20 combat engine: initiative, turn order, attack resolution."""

from entities import Creature


class CombatManager:
    def __init__(self):
        self.active = False
        self.turn_order: list[Creature] = []
        self.current_turn_idx = 0
        self.round_number = 0
        self.log: list[str] = []

    def start_combat(self, combatants: list[Creature]):
        self.active = True
        self.round_number = 1
        self.log = ["--- Combat Started ---"]

        # Roll initiative
        initiatives = []
        for c in combatants:
            if c.alive:
                init = c.roll_initiative()
                initiatives.append((init, c))
                self.log.append(f"{c.name} rolls initiative: {init}")

        # Sort descending
        initiatives.sort(key=lambda x: x[0], reverse=True)
        self.turn_order = [c for _, c in initiatives]
        self.current_turn_idx = 0

        if self.turn_order:
            self.turn_order[0].start_turn()
            self.log.append(f"Round {self.round_number}: {self.turn_order[0].name}'s turn")

    @property
    def current_creature(self) -> Creature | None:
        if not self.active or not self.turn_order:
            return None
        return self.turn_order[self.current_turn_idx]

    def next_turn(self):
        # Remove dead creatures
        self.turn_order = [c for c in self.turn_order if c.alive]

        if not self.turn_order:
            self.end_combat()
            return

        self.current_turn_idx = (self.current_turn_idx + 1) % len(self.turn_order)

        if self.current_turn_idx == 0:
            self.round_number += 1

        current = self.turn_order[self.current_turn_idx]
        current.start_turn()
        self.log.append(f"Round {self.round_number}: {current.name}'s turn")

    def end_combat(self):
        self.active = False
        self.log.append("--- Combat Ended ---")
        self.turn_order = []

    def player_attack(self, attacker: Creature, target: Creature) -> list[str]:
        """Resolve a player attack against a target."""
        log = []
        attack_roll = attacker.roll_attack()

        if attack_roll >= target.ac:
            damage = attacker.roll_damage()
            target.take_damage(damage)
            log.append(f"{attacker.name} hits {target.name} for {damage} damage! (roll: {attack_roll} vs AC {target.ac})")
            if not target.alive:
                log.append(f"{target.name} is defeated!")
        else:
            log.append(f"{attacker.name} misses {target.name}. (roll: {attack_roll} vs AC {target.ac})")

        attacker.has_action = False
        return log

    def check_combat_end(self) -> bool:
        enemies_alive = any(c.alive and c.token_type == "enemy" for c in self.turn_order)
        player_alive = any(c.alive and c.token_type == "player" for c in self.turn_order)

        if not enemies_alive:
            self.log.append("All enemies defeated! Victory!")
            self.end_combat()
            return True
        if not player_alive:
            self.log.append("Player defeated! Game over.")
            self.end_combat()
            return True
        return False
```

- [ ] **Step 6: Create game_engine.py**

```python
"""Game state machine: exploration and combat modes."""

from enum import Enum
from entities import Creature
from combat import CombatManager
from ai import ai_turn, manhattan_dist
from config import COMBAT_DETECT_RANGE


class GameState(Enum):
    EXPLORATION = "exploration"
    COMBAT = "combat"
    GAME_OVER = "game_over"


class GameEngine:
    def __init__(self, game_map, creatures):
        self.state = GameState.EXPLORATION
        self.game_map = game_map
        self.creatures = creatures
        self.player = next((c for c in creatures if c.token_type == "player"), None)
        self.combat = CombatManager()
        self.log: list[str] = []

    def update(self):
        if self.state == GameState.EXPLORATION:
            self._check_combat_trigger()
        elif self.state == GameState.COMBAT:
            self._process_combat_turn()

    def _check_combat_trigger(self):
        if self.player is None or not self.player.alive:
            return

        for c in self.creatures:
            if c.token_type != "enemy" or not c.alive:
                continue
            if c.z != self.player.z:
                continue
            dist = manhattan_dist(c.x, c.y, self.player.x, self.player.y)
            if dist <= COMBAT_DETECT_RANGE:
                # Check line of sight (simplified: just distance for now)
                self._enter_combat()
                return

    def _enter_combat(self):
        self.state = GameState.COMBAT
        combatants = [self.player] + [
            c for c in self.creatures
            if c.token_type == "enemy" and c.alive and c.z == self.player.z
            and manhattan_dist(c.x, c.y, self.player.x, self.player.y) <= COMBAT_DETECT_RANGE
        ]
        self.combat.start_combat(combatants)
        self.log.extend(self.combat.log[-len(combatants)-1:])

    def _process_combat_turn(self):
        current = self.combat.current_creature
        if current is None:
            self.state = GameState.EXPLORATION
            return

        # Only auto-process enemy turns
        if current.token_type == "enemy":
            walk = self.game_map.walkability.get(current.z)
            if walk is not None:
                turn_log = ai_turn(current, self.player, walk, self.creatures)
                self.log.extend(turn_log)
                self.combat.log.extend(turn_log)

            if self.combat.check_combat_end():
                if not self.player.alive:
                    self.state = GameState.GAME_OVER
                else:
                    self.state = GameState.EXPLORATION
                return

            self.combat.next_turn()

    def player_end_turn(self):
        if self.state != GameState.COMBAT:
            return
        current = self.combat.current_creature
        if current and current.token_type == "player":
            self.combat.next_turn()

    def player_attack_target(self, target):
        if self.state != GameState.COMBAT:
            return
        current = self.combat.current_creature
        if current and current.token_type == "player" and current.has_action:
            if manhattan_dist(current.x, current.y, target.x, target.y) <= 1:
                log = self.combat.player_attack(current, target)
                self.log.extend(log)
                self.combat.log.extend(log)
                self.combat.check_combat_end()
```

- [ ] **Step 7: Create renderer.py**

```python
"""Tile-based renderer with layer compositing and parallax."""

import pygame
import numpy as np
from PIL import Image
from config import (TILE_SIZE, COLOR_PLAYER, COLOR_PLAYER_BORDER, COLOR_ENEMY,
                    COLOR_ENEMY_BORDER, COLOR_NPC, COLOR_NPC_BORDER,
                    COLOR_HP_GREEN, COLOR_HP_RED, COLOR_HP_BG, COLOR_GRID,
                    COLOR_TRANSITION, TOKEN_RADIUS, TOKEN_BORDER, COLOR_BLACK)
from fog_of_war import UNEXPLORED, EXPLORED, VISIBLE


def pil_to_surface(pil_image):
    """Convert PIL Image to pygame Surface."""
    mode = pil_image.mode
    size = pil_image.size
    data = pil_image.tobytes()
    return pygame.image.fromstring(data, size, mode)


class Renderer:
    def __init__(self, screen, game_map):
        self.screen = screen
        self.game_map = game_map
        self.show_grid = False

        # Convert terrain images to pygame surfaces
        for z, img in game_map.terrain_images.items():
            game_map.terrain_surfaces[z] = pil_to_surface(img)

    def render(self, camera, creatures, fog, player_z, engine):
        self.screen.fill(COLOR_BLACK)

        # Draw z-level below current (dimmed)
        below_z = player_z - 1
        if below_z in self.game_map.terrain_surfaces:
            self._draw_terrain(camera, below_z, alpha=128)

        # Draw current z-level
        if player_z in self.game_map.terrain_surfaces:
            self._draw_terrain(camera, player_z, alpha=255)

        # Draw transitions (stairs markers)
        for t in self.game_map.transitions:
            if t["from_z"] == player_z or t["to_z"] == player_z:
                wx = t["x"] * TILE_SIZE + TILE_SIZE // 2
                wy = t["y"] * TILE_SIZE + TILE_SIZE // 2
                sx, sy = camera.world_to_screen(wx, wy)
                size = max(3, int(TILE_SIZE * camera.zoom * 0.4))
                pygame.draw.rect(self.screen, COLOR_TRANSITION,
                                (sx - size, sy - size, size * 2, size * 2), 2)

        # Draw entities (tokens)
        for creature in creatures:
            if creature.z != player_z or not creature.alive:
                continue
            self._draw_token(camera, creature)

        # Apply fog of war
        if fog.enabled:
            self._draw_fog(camera, fog, player_z)

        # Grid overlay
        if self.show_grid:
            self._draw_grid(camera)

    def _draw_terrain(self, camera, z, alpha=255):
        surface = self.game_map.terrain_surfaces.get(z)
        if surface is None:
            return

        z_offset = z - (getattr(camera, '_player_z', 0))
        # Scale surface to current zoom
        w = int(surface.get_width() * camera.zoom)
        h = int(surface.get_height() * camera.zoom)
        if w < 1 or h < 1:
            return

        scaled = pygame.transform.scale(surface, (w, h))

        if alpha < 255:
            scaled.set_alpha(alpha)

        sx, sy = camera.world_to_screen(0, 0, z_offset)
        self.screen.blit(scaled, (sx, sy))

    def _draw_token(self, camera, creature):
        wx = creature.x * TILE_SIZE + TILE_SIZE // 2
        wy = creature.y * TILE_SIZE + TILE_SIZE // 2
        sx, sy = camera.world_to_screen(wx, wy)
        r = max(3, int(TOKEN_RADIUS * camera.zoom))

        if creature.token_type == "player":
            color, border = COLOR_PLAYER, COLOR_PLAYER_BORDER
        elif creature.token_type == "enemy":
            color, border = COLOR_ENEMY, COLOR_ENEMY_BORDER
        else:
            color, border = COLOR_NPC, COLOR_NPC_BORDER

        pygame.draw.circle(self.screen, border, (sx, sy), r + TOKEN_BORDER)
        pygame.draw.circle(self.screen, color, (sx, sy), r)

        # Letter label
        font = pygame.font.SysFont("Arial", max(8, int(10 * camera.zoom)), bold=True)
        letter = creature.token_type[0].upper()
        text = font.render(letter, True, (255, 255, 255))
        text_rect = text.get_rect(center=(sx, sy))
        self.screen.blit(text, text_rect)

        # HP bar (only if damaged)
        if creature.hp < creature.max_hp:
            bar_w = max(10, int(20 * camera.zoom))
            bar_h = max(2, int(3 * camera.zoom))
            bar_x = sx - bar_w // 2
            bar_y = sy - r - bar_h - 4
            pygame.draw.rect(self.screen, COLOR_HP_BG, (bar_x, bar_y, bar_w, bar_h))
            fill_w = int(bar_w * creature.hp_pct)
            hp_color = COLOR_HP_GREEN if creature.hp_pct > 0.5 else COLOR_HP_RED
            pygame.draw.rect(self.screen, hp_color, (bar_x, bar_y, fill_w, bar_h))

    def _draw_fog(self, camera, fog, player_z):
        fog_state = fog.get_or_create(player_z)
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)

        x1, y1, x2, y2 = camera.visible_tile_range()
        tile_screen_size = max(1, int(TILE_SIZE * camera.zoom))

        for ty in range(y1, y2):
            for tx in range(x1, x2):
                if 0 <= ty < fog.height and 0 <= tx < fog.width:
                    state = fog_state[ty, tx]
                    if state == UNEXPLORED:
                        sx, sy = camera.world_to_screen(tx * TILE_SIZE, ty * TILE_SIZE)
                        pygame.draw.rect(overlay, (0, 0, 0, 255),
                                        (sx, sy, tile_screen_size, tile_screen_size))
                    elif state == EXPLORED:
                        sx, sy = camera.world_to_screen(tx * TILE_SIZE, ty * TILE_SIZE)
                        pygame.draw.rect(overlay, (0, 0, 0, 140),
                                        (sx, sy, tile_screen_size, tile_screen_size))

        self.screen.blit(overlay, (0, 0))

    def _draw_grid(self, camera):
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        x1, y1, x2, y2 = camera.visible_tile_range()
        for tx in range(x1, x2 + 1):
            sx, _ = camera.world_to_screen(tx * TILE_SIZE, 0)
            pygame.draw.line(overlay, (255, 255, 255, 40), (sx, 0), (sx, self.screen.get_height()))
        for ty in range(y1, y2 + 1):
            _, sy = camera.world_to_screen(0, ty * TILE_SIZE)
            pygame.draw.line(overlay, (255, 255, 255, 40), (0, sy), (self.screen.get_width(), sy))
        self.screen.blit(overlay, (0, 0))

    def toggle_grid(self):
        self.show_grid = not self.show_grid
```

- [ ] **Step 8: Create ui_overlay.py**

```python
"""HUD overlay: combat log, stats panel, minimap, mode indicator."""

import pygame
from config import (COLOR_UI_BG, COLOR_UI_TEXT, COLOR_UI_GOLD, WINDOW_WIDTH, WINDOW_HEIGHT,
                    COLOR_PLAYER, COLOR_ENEMY, COLOR_NPC, COLOR_HP_GREEN, COLOR_HP_RED)


class UIOverlay:
    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.SysFont("Consolas", 13)
        self.font_small = pygame.font.SysFont("Consolas", 11)
        self.font_title = pygame.font.SysFont("Arial", 16, bold=True)

    def render(self, engine, player, creatures, camera):
        sw, sh = self.screen.get_size()

        # Mode indicator (top-left)
        mode_text = engine.state.value.upper()
        mode_color = COLOR_UI_GOLD if engine.state.value == "combat" else (100, 200, 100)
        self._draw_text(mode_text, 10, 10, mode_color, self.font_title)

        # Z-level indicator
        z_text = f"Z: {player.z}" if player else "Z: ?"
        self._draw_text(z_text, 10, 32, COLOR_UI_TEXT, self.font)

        # Perspective mode
        persp = "PARALLAX" if camera.perspective_mode else "TOP-DOWN"
        self._draw_text(persp, 10, 48, (150, 150, 150), self.font_small)

        # Player stats (top-right)
        if player and player.alive:
            self._draw_stats_panel(player, sw - 200, 10)

        # Combat log (bottom)
        if engine.log:
            self._draw_combat_log(engine.log, 10, sh - 150, sw - 220, 140)

        # Combat turn order (right side during combat)
        if engine.state.value == "combat" and engine.combat.turn_order:
            self._draw_turn_order(engine.combat, sw - 200, 120)

    def _draw_stats_panel(self, creature, x, y):
        panel_w, panel_h = 190, 100
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((26, 26, 46, 220))
        pygame.draw.rect(panel, COLOR_UI_GOLD, (0, 0, panel_w, panel_h), 1)

        # Name
        name_surf = self.font_title.render(creature.name, True, COLOR_UI_GOLD)
        panel.blit(name_surf, (8, 5))

        # HP bar
        bar_y = 28
        bar_w = panel_w - 16
        bar_h = 10
        pygame.draw.rect(panel, (40, 40, 40), (8, bar_y, bar_w, bar_h))
        fill_w = int(bar_w * creature.hp_pct)
        hp_color = COLOR_HP_GREEN if creature.hp_pct > 0.5 else COLOR_HP_RED
        pygame.draw.rect(panel, hp_color, (8, bar_y, fill_w, bar_h))
        hp_text = self.font_small.render(f"HP: {creature.hp}/{creature.max_hp}", True, COLOR_UI_TEXT)
        panel.blit(hp_text, (8, bar_y + 12))

        # Stats
        stats_text = f"AC:{creature.ac}  STR:{creature.strength}  DEX:{creature.dexterity}"
        panel.blit(self.font_small.render(stats_text, True, (180, 180, 180)), (8, 56))
        stats_text2 = f"SPD:{creature.speed}  ATK:{creature.atk_dice}"
        panel.blit(self.font_small.render(stats_text2, True, (180, 180, 180)), (8, 72))

        self.screen.blit(panel, (x, y))

    def _draw_combat_log(self, log_lines, x, y, w, h):
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((26, 26, 46, 200))
        pygame.draw.rect(panel, (80, 80, 80), (0, 0, w, h), 1)

        # Show last N lines that fit
        line_h = 14
        max_lines = h // line_h - 1
        visible = log_lines[-max_lines:]

        for i, line in enumerate(visible):
            color = COLOR_UI_TEXT
            if "hits" in line.lower():
                color = COLOR_HP_RED
            elif "misses" in line.lower():
                color = (150, 150, 150)
            elif "defeated" in line.lower():
                color = COLOR_UI_GOLD
            text = self.font_small.render(line[:80], True, color)
            panel.blit(text, (6, 4 + i * line_h))

        self.screen.blit(panel, (x, y))

    def _draw_turn_order(self, combat, x, y):
        panel_w = 190
        entries = combat.turn_order[:8]
        panel_h = 20 + len(entries) * 22

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((26, 26, 46, 220))
        pygame.draw.rect(panel, COLOR_UI_GOLD, (0, 0, panel_w, panel_h), 1)

        header = self.font_small.render("Turn Order", True, COLOR_UI_GOLD)
        panel.blit(header, (8, 4))

        for i, creature in enumerate(entries):
            cy = 20 + i * 22
            is_current = (i == combat.current_turn_idx)
            color_map = {"player": COLOR_PLAYER, "enemy": COLOR_ENEMY, "npc": COLOR_NPC}
            dot_color = color_map.get(creature.token_type, COLOR_UI_TEXT)

            if is_current:
                pygame.draw.rect(panel, (40, 60, 80), (2, cy, panel_w - 4, 20))

            pygame.draw.circle(panel, dot_color, (16, cy + 10), 5)
            name_text = self.font_small.render(f"{creature.name} ({creature.hp}hp)", True, COLOR_UI_TEXT)
            panel.blit(name_text, (28, cy + 2))

        self.screen.blit(panel, (x, y))

    def _draw_text(self, text, x, y, color, font):
        surf = font.render(text, True, color)
        self.screen.blit(surf, (x, y))
```

- [ ] **Step 9: Create main.py (game loop)**

```python
"""Pygame playtest viewer entry point."""

import sys
import os
import pygame

# Ensure viewer package imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from config import *
from map_loader import load_map
from camera import Camera
from renderer import Renderer
from fog_of_war import FogOfWar
from entities import Creature
from game_engine import GameEngine
from ui_overlay import UIOverlay


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <map_directory>")
        print("  map_directory should contain map_data.json and z_*.png files")
        sys.exit(1)

    map_dir = sys.argv[1]
    if not os.path.exists(os.path.join(map_dir, "map_data.json")):
        print(f"Error: {map_dir}/map_data.json not found")
        sys.exit(1)

    # Init pygame
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    # Load map
    game_map = load_map(map_dir)

    # Create creatures from spawns
    creatures = [Creature.from_spawn(s) for s in game_map.spawns]
    player = next((c for c in creatures if c.token_type == "player"), None)

    if player is None:
        print("Warning: No player spawn found. Creating default at (16, 16).")
        player = Creature(name="Hero", x=16, y=16, z=0, token_type="player",
                          hp=30, max_hp=30, ac=15, strength=16, dexterity=14,
                          constitution=14, speed=6, atk_dice="1d8+3")
        creatures.insert(0, player)

    # Init systems
    camera = Camera(game_map.width, game_map.height)
    renderer = Renderer(screen, game_map)
    fog = FogOfWar(game_map.width, game_map.height)
    engine = GameEngine(game_map, creatures)
    ui = UIOverlay(screen)

    # Middle mouse panning state
    panning = False
    pan_start = (0, 0)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == KEY_QUIT:
                    running = False

                elif event.key == KEY_TOGGLE_PERSPECTIVE:
                    camera.toggle_perspective()

                elif event.key == KEY_TOGGLE_GRID:
                    renderer.toggle_grid()

                elif event.key == KEY_TOGGLE_FOG:
                    fog.toggle()

                elif event.key == KEY_ZLEVEL_UP:
                    player.z += 1

                elif event.key == KEY_ZLEVEL_DOWN:
                    player.z -= 1

                elif event.key == KEY_END_TURN:
                    engine.player_end_turn()

                elif event.key == KEY_INTERACT:
                    # Check for transitions at player position
                    for t in game_map.transitions:
                        if t["from_z"] == player.z and t["x"] == player.x and t["y"] == player.y:
                            player.z = t["to_z"]
                            engine.log.append(f"Used {t['type']} to z={t['to_z']}")
                            break

                # Movement (exploration mode)
                elif engine.state.value == "exploration":
                    dx, dy = 0, 0
                    if event.key in KEY_MOVE_UP:
                        dy = -1
                    elif event.key in KEY_MOVE_DOWN:
                        dy = 1
                    elif event.key in KEY_MOVE_LEFT:
                        dx = -1
                    elif event.key in KEY_MOVE_RIGHT:
                        dx = 1

                    if dx or dy:
                        nx, ny = player.x + dx, player.y + dy
                        walk = game_map.walkability.get(player.z)
                        if walk is not None and 0 <= nx < game_map.width and 0 <= ny < game_map.height:
                            if walk[ny, nx]:
                                player.x, player.y = nx, ny

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 4:  # scroll up
                    camera.zoom_in()
                elif event.button == 5:  # scroll down
                    camera.zoom_out()
                elif event.button == 2:  # middle mouse
                    panning = True
                    pan_start = event.pos
                elif event.button == 1 and engine.state.value == "combat":
                    # Click to attack adjacent enemy
                    mx, my = camera.screen_to_world(*event.pos)
                    tile_x = int(mx / TILE_SIZE)
                    tile_y = int(my / TILE_SIZE)
                    for c in creatures:
                        if (c.token_type == "enemy" and c.alive
                            and c.x == tile_x and c.y == tile_y
                            and c.z == player.z):
                            engine.player_attack_target(c)
                            break

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 2:
                    panning = False

            elif event.type == pygame.MOUSEMOTION:
                if panning:
                    dx = event.pos[0] - pan_start[0]
                    dy = event.pos[1] - pan_start[1]
                    camera.pan(-dx, -dy)
                    pan_start = event.pos
                # Update parallax angle based on mouse position
                if camera.perspective_mode:
                    sw, sh = screen.get_size()
                    camera.angle_x = (event.pos[0] / sw - 0.5) * 2
                    camera.angle_y = (event.pos[1] / sh - 0.5) * 2

            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

        # Update game state
        engine.update()

        # Update fog of war
        fog.update(player.x, player.y, player.z, game_map.walkability)

        # Camera follow player
        camera._player_z = player.z
        camera.follow(player.x * TILE_SIZE, player.y * TILE_SIZE)
        camera.update()

        # Render
        renderer.render(camera, creatures, fog, player.z, engine)
        ui.render(engine, player, creatures, camera)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
```

- [ ] **Step 10: Test viewer launches with a generated map**

```bash
cd "C:/Dev/Map Generator"
.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, 'mapgen_agents')
from map_generator import MapGenerator
gen = MapGenerator(verbose=False)
gen.generate(goal='A village', map_type='village', biome='forest', size='small_encounter', seed=42)
print('Map generated at ./output/')
"
.venv/Scripts/python.exe mapgen_agents/viewer/main.py ./output/
```

Expected: Pygame window opens showing the village map with a blue player token. WASD moves the player. Fog of war reveals as you explore. Tab toggles parallax. Red enemy tokens visible on the map.

- [ ] **Step 11: Commit**

```bash
git add mapgen_agents/viewer/ requirements.txt
git commit -m "feat: pygame playtest viewer with movement, fog of war, parallax camera, d20 combat"
```

---

## Phase 5: GUI Integration

### Task 8: Add Playtest Button to GUI

**Files:**
- Modify: `mapgen_agents/gui.py`

- [ ] **Step 1: Add Playtest button after Generate Map**

In `_build_actions`, add a Playtest button:

```python
self.playtest_btn = tk.Button(
    btn_row, text="Playtest", command=self._on_playtest,
    bg=BG_CARD, fg=GOLD, activebackground=BG_LIGHT,
    activeforeground=GOLD, relief="flat",
    font=("Segoe UI", 9, "bold"), pady=3, cursor="hand2",
)
self.playtest_btn.pack(fill="x", pady=(2, 0))
```

Add the handler:

```python
def _on_playtest(self):
    """Launch the pygame viewer for the last generated map."""
    if self.last_result is None:
        messagebox.showinfo("Playtest", "Generate a map first.")
        return
    output_path = self.last_result.get("output_path", "")
    if not output_path:
        messagebox.showinfo("Playtest", "No output path found.")
        return
    map_dir = os.path.dirname(os.path.abspath(output_path))
    if not os.path.exists(os.path.join(map_dir, "map_data.json")):
        messagebox.showinfo("Playtest", "map_data.json not found. Regenerate the map.")
        return

    import subprocess
    viewer_path = os.path.join(os.path.dirname(__file__), "viewer", "main.py")
    python_exe = sys.executable
    subprocess.Popen([python_exe, viewer_path, map_dir])
    self._log("Launched playtest viewer")
```

- [ ] **Step 2: Test GUI launches viewer**

Launch the GUI, generate a map, click Playtest. Pygame window should open.

- [ ] **Step 3: Commit**

```bash
git add mapgen_agents/gui.py
git commit -m "feat: add Playtest button to GUI that launches pygame viewer"
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | Task 1 | ZLevel data model + backwards-compat SharedState |
| 2 | Tasks 2-3 | SpawnAgent + multi-floor structure generation |
| 3 | Task 4 | Per-layer PNG export + JSON map data |
| 4 | Tasks 5-7 | Pygame viewer: config, entities, camera, fog, renderer, AI, combat, UI, main loop |
| 5 | Task 8 | GUI Playtest button integration |

Total: 8 tasks, ~20 new files, ~2500 lines of new code.

# Layered Renderer + Playtest Viewer Design

**Date:** 2026-04-04
**Status:** Approved
**Scope:** Multi-layer z-level system, high-fidelity top-down renderer with parallax depth, pygame-based playtest viewer with d20 combat, Unity layer export

---

## 1. Overview

Transform the Map Generator from a flat 2D map renderer into a layered, multi-level system with an interactive playtest viewer. Buildings have multiple floors (ground, upper, roof, basement). Dungeons stack arbitrarily deep. A pygame-based viewer lets you walk a player token through the map, toggle layer visibility, and engage in turn-based combat with d20-style rules.

### Target Hardware
- NVIDIA RTX 5090 (32GB VRAM, CUDA 13.2)
- AMD Ryzen 9 9950X3D (16-core)
- 64GB RAM
- OpenGL-accelerated rendering via pygame

## 2. Layer Data Model

### Z-Level Convention
- `z=0` is ground level / outdoor terrain (always exists)
- `z=+N` goes up: upper floors, roofs, battlements
- `z=-N` goes down: basements, dungeon levels, deep caves
- No hard limit in either direction (hybrid variable/infinite)

### Per-Structure Layer Counts
| Structure Type | Layers | Z-Range |
|---------------|--------|---------|
| Cottage/House | 2 | 0 (ground), +1 (roof) |
| Shop/Tavern | 2-3 | 0 (ground), +1 (upper/storage), +2 (roof) |
| Castle | 4-8 | -2 (vault) to +3 (battlements) |
| Fort/Tower | 3-5 | 0 (ground) to +4 (top) |
| Dungeon | 2-N | 0 (entrance), -1 to -N (sub-levels) |
| Cave | 2-N | 0 (entrance), -1 to -N (depths) |
| Temple/Church | 2-3 | -1 (crypt), 0 (nave), +1 (belfry) |
| Mine | 2-N | 0 (entrance), -1 to -N (shafts) |
| Mega Dungeon | Unlimited | 0 to -20+ |

### Data Classes

```python
@dataclass
class ZLevel:
    z: int
    terrain_color: np.ndarray    # uint8[H,W,3]
    walkability: np.ndarray      # bool[H,W]
    structure_mask: np.ndarray   # bool[H,W]
    water_mask: np.ndarray       # bool[H,W]
    entities: list[Entity]
    labels: list[Label]

@dataclass
class Transition:
    x: int
    y: int
    from_z: int
    to_z: int
    transition_type: str  # "stairs_up", "stairs_down", "ladder", "trapdoor", "entrance"

@dataclass
class SpawnPoint:
    x: int
    y: int
    z: int
    token_type: str       # "player", "enemy", "npc"
    name: str             # "Goblin Grunt", "Village Blacksmith"
    stats: dict           # HP, AC, STR, DEX, CON, SPD, ATK
    ai_behavior: str      # "patrol", "guard", "chase", "static"
```

### Layer Visibility Rule
When player is at z=N:
- **Show fully:** z=N (current level)
- **Show dimmed (50%):** z=N-1 (level below, for spatial context)
- **Hide:** all other levels

## 3. Camera & Perspective

### Top-Down with Parallax Depth
The map renders top-down. Higher z-levels are offset slightly from the camera position to create a subtle depth effect (like looking at stacked transparent sheets from slightly off-center).

**Parallax formula:**
```
offset_x = (layer_z - player_z) * parallax_strength * camera_angle_x
offset_y = (layer_z - player_z) * parallax_strength * camera_angle_y
```
Where `parallax_strength` is ~5% of tile size and `camera_angle` is controlled by the user.

### Camera Controls
- **Mouse wheel:** Zoom in/out
- **Middle mouse drag:** Pan camera
- **Tab:** Toggle between pure top-down and parallax perspective mode
- **Camera auto-follows player** with smooth interpolation

## 4. Playtest Viewer (Pygame)

### Architecture
11 modules in `viewer/`:

| Module | Purpose |
|--------|---------|
| `main.py` | Entry point, 60fps game loop, event pump |
| `map_loader.py` | Load layered JSON + per-level PNGs |
| `renderer.py` | Tile-based OpenGL-accelerated drawing, layer compositing, parallax |
| `camera.py` | Pan, zoom, player-follow, parallax offset calculation |
| `fog_of_war.py` | Three-state visibility (unexplored/explored/visible), LOS raycasting |
| `game_engine.py` | State machine: exploration mode vs combat mode |
| `combat.py` | D20 rules engine: initiative, attack rolls, damage, turn order |
| `entities.py` | Player, Enemy, NPC classes with stat blocks and movement |
| `ai.py` | Enemy behavior: chase, patrol, guard, attack if adjacent |
| `ui_overlay.py` | HUD: HP bars, combat log, minimap, stats panel |
| `config.py` | Keybindings, tile size, colors, token settings |

### Rendering Pipeline (per frame)
1. Camera calculates visible tile range + parallax offsets
2. Draw z-level below current (dimmed 50%)
3. Draw current z-level terrain + structures
4. Draw entities (player/enemy/NPC tokens, furniture, doors, stairs)
5. Apply fog of war mask (black=unexplored, dim=explored, clear=visible)
6. Draw UI overlay (HP bars, combat log, minimap, stats)
7. Flip display buffer (vsync)

### Token Types
- **Player (blue circle, "P"):** WASD movement. User-controlled.
- **Enemy (red circle, "E"):** Auto-placed by generator. Basic AI. Hostile.
- **NPC (gold circle, "N"):** Auto-placed. Non-hostile. Interact with F key.

### Controls
| Key | Action |
|-----|--------|
| WASD / Arrows | Move player |
| F | Interact (door, NPC, stairs) |
| Space | End turn (combat mode) |
| Tab | Toggle perspective mode |
| Mouse wheel | Zoom in/out |
| Middle mouse drag | Pan camera |
| [ / ] | Force z-level up/down |
| G | Toggle grid overlay |
| V | Toggle fog of war |
| Esc | Menu / quit |
| Left click | Move to tile (combat) / Attack enemy (combat) |

## 5. Combat System

### Stat Block
All creatures (player, enemies, NPCs) share:
- **HP:** Hit points (health pool)
- **AC:** Armor class (hit threshold, typically 10-20)
- **STR:** Strength -- melee attack modifier, melee damage modifier
- **DEX:** Dexterity -- initiative modifier, ranged attack modifier, AC modifier
- **CON:** Constitution -- HP bonus per level
- **SPD:** Speed -- movement tiles per turn (default 6 = 30ft in 5ft squares)
- **ATK:** Attack dice string (e.g., "1d8+3")
- **INT/WIS/CHA:** Tracked but not mechanically used in v1

### Combat Flow
1. **Trigger:** Enemy enters detection range (default 12 tiles) with line-of-sight
2. **Initiative:** Each creature rolls d20 + DEX modifier. Sorted high-to-low.
3. **Turn cycle:**
   - Active creature gets SPD tiles of movement + 1 action (attack or interact)
   - **Attack:** d20 + STR/DEX mod >= target AC = hit. Roll ATK damage dice.
   - **Move:** Click tile within SPD range. Pathfinding auto-routes.
4. **Enemy AI turn:** Move toward nearest visible player. Attack if adjacent.
5. **End:** All enemies at 0 HP. Return to exploration mode.

### Enemy Scaling
Enemies are placed and scaled by the spawn_agent based on map type:
- **Village/Town:** Few weak enemies (bandits, wolves). CR 1/4 to 1.
- **Dungeon/Cave:** Moderate enemies per room. CR 1-5.
- **Castle/Fort:** Guards with decent AC. CR 2-4.
- **Mega Dungeon:** Difficulty increases per z-level depth.

## 6. Map Generator Changes

### Backwards Compatibility Strategy
Existing agents (TerrainAgent, WaterAgent, PathfindingAgent, LabelingAgent) work unchanged. They write to `shared_state.terrain_color` etc., which maps to the ground ZLevel (z=0) via `@property` accessors.

### Agent Changes

| Agent | Change | Effort |
|-------|--------|--------|
| shared_state.py | Add ZLevel, Transition, SpawnPoint. Wrap ground arrays. Backwards-compat properties. | Medium |
| structure_agent.py | Multi-floor building generation. Create ZLevels per floor. Place stairs/transitions. | Large |
| NEW: spawn_agent.py | Place player spawn, enemies, NPCs with stat blocks. Scale by map type. | Medium |
| asset_agent.py | Place indoor assets on correct z-level. | Small |
| renderer_agent.py | Output per-layer PNGs + flattened preview. | Medium |
| planner.py | Add spawn_agent to DAG templates after structures. | Small |
| orchestrator.py | Register SpawnAgent. | Trivial |
| Unity exporters | Export z-level data, transitions, spawns to JSON. | Medium |
| terrain_agent.py | No change. | None |
| water_agent.py | No change. | None |
| pathfinding_agent.py | No change. | None |
| labeling_agent.py | No change. | None |

### Output Format
```
output/village_forest_42_20260404_065500/
  preview.png               # Flattened composite (for GUI thumbnail)
  map_data.json             # Full layered data for viewer
    ├─ config: {size, biome, seed, map_type, ...}
    ├─ z_levels: [
    │    {z: -1, terrain_png: "z_neg1.png", walkability: [...], entities: [...]}
    │    {z: 0,  terrain_png: "z_0.png",    walkability: [...], entities: [...]}
    │    {z: 1,  terrain_png: "z_1.png",    walkability: [...], entities: [...]}
    │  ]
    ├─ transitions: [{x, y, from_z, to_z, type}, ...]
    ├─ spawns: [{x, y, z, token_type, name, stats, ai_behavior}, ...]
    └─ labels: [{x, y, z, text, category}, ...]
  z_neg1.png                # Terrain render for z=-1
  z_0.png                   # Terrain render for z=0 (ground)
  z_1.png                   # Terrain render for z=1 (roofs/upper)
  unity_export/             # Enhanced Unity files with layer data
```

## 7. GUI Integration

The existing tkinter GUI gets a **"Playtest"** button next to "Generate Map". After generation:
1. Click "Playtest" to launch `viewer/main.py` as a subprocess
2. The viewer opens a pygame window, loads the map data
3. Player token spawns at the designated spawn point
4. Viewer runs independently; closing it returns to the GUI

## 8. Dependencies

**New:**
- `pygame>=2.5.0` -- Playtest viewer (game loop, rendering, input)

**Existing (unchanged):**
- numpy, Pillow, anthropic

## 9. Non-Goals (v1)

- Multiplayer / networked play
- Procedural quest generation
- Inventory / equipment system
- Spell/ability system beyond basic melee/ranged attacks
- Save/load game state
- Sound effects or music
- Particle effects or dynamic lighting (future CUDA potential)

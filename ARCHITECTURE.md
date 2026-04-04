# Map Generator Architecture

## Overview

A 3-tier multi-agent procedural map generation system designed for Unity game engine, powered by Anthropic's Claude API. The system decomposes high-level natural language goals into Directed Acyclic Graphs (DAGs) of subtasks, orchestrates execution through a project manager agent, and delegates work to specialized low-level agents that generate terrain, water, paths, structures, assets, labels, and export to Unity-compatible formats.

## System Architecture

```
                    +---------------------------+
                    |    MapGenerator (API)      |
                    |  map_generator.py          |
                    +---------------------------+
                                |
               +----------------+----------------+
               |                                 |
    +----------v----------+           +----------v----------+
    |  StrategicPlanner   |           |     SharedState      |
    |  (Tier 1 - Planning)|           |  (Central Data Layer) |
    |  planner.py         |           |  shared_state.py      |
    +---------------------+           +-----------------------+
               |                                 ^
               v                                 |
    +---------------------+                      |
    |    Orchestrator      |       reads/writes   |
    |  (Tier 2 - Manage)  |<--------------------->
    |  orchestrator.py     |
    +---------------------+
               |
               v
    +---------------------+
    |  Execution Agents    |
    |  (Tier 3 - Execute)  |
    |  agents/*.py         |
    +---------------------+
```

## Tier 1: Strategic Planner

The planner decomposes a natural language goal into a TaskDAG. It tries Claude API first for creative, context-aware planning, then falls back to template-based planning if no API key is available.

**30 supported map types** organized by category:

| Category | Map Types |
|----------|-----------|
| Settlements | village, town, city |
| Fortifications | castle, fort, tower |
| Underground/Interior | dungeon, cave, mine, maze, treasure_room |
| Religious/Burial | crypt, tomb, graveyard, temple, church |
| Commercial/Industrial | shop, shopping_center, factory |
| Waterfront | dock |
| Combat | arena |
| Field/Outdoor | wilderness, camp, outpost, rest_area, crash_site |
| Large Scale | biomes, region, open_world, world_box |

**Size presets:** small_encounter (256), medium_encounter (512), large_encounter (768), standard (512), large (1024), region (1024), open_world (1536)

## Tier 2: Orchestrator

Validates the DAG (cycle detection), performs topological sort to determine execution order, dispatches tasks level-by-level to the appropriate execution agents, and handles retry logic (3 attempts per task).

## Tier 3: Execution Agents

### TerrainAgent
Generates elevation and moisture maps using multi-octave Perlin noise. Supports 9 biomes (forest, mountain, desert, swamp, plains, tundra, volcanic, cave, dungeon) with distinct presets and color palettes. Uses cellular automata carving for cave/dungeon biomes.

### WaterAgent
5 water feature types:

- **Rivers** — Gradient descent from high-elevation edge points, flowing downhill with controlled randomness
- **Streams** — Narrower and shorter than rivers, more meandering, start from mid-elevation interior points
- **Lakes** — Elliptical bodies in low-elevation areas with noise for organic shorelines
- **Ponds** — Small circular water bodies, much smaller than lakes
- **Oceans** — Coastline along one map edge with multi-frequency noise and beach/sand strips

### PathfindingAgent
A* pathfinding with elevation cost. Generates spread points using farthest-point sampling for POI distribution, then connects them with an MST-like road network.

### StructureAgent
23 structure types with specialized generators:

- **BSP rooms** — Dungeon chamber generation
- **Recursive backtracker** — Maze generation
- **Tunnel carving** — Mine shaft and branch networks
- **Perimeter walls** — Castle, fort, temple, church, graveyard
- **Circular footprints** — Tower, arena
- **Impact craters** — Crash site with debris scatter
- **Waterfront piers** — Dock with pier extensions into water
- **Industrial layouts** — Factory with machinery blocks
- **Religious interiors** — Temple columns/sanctum, church nave/pews/bell tower
- **Burial complexes** — Crypt with sarcophagi, tomb with sealed passages
- **Generic placement** — Village, town, city, shop, shopping_center, rest_area, outpost, camp

### AssetAgent
Poisson disk sampling for natural asset distribution. 20+ asset palettes keyed by biome/map type, each defining (type, color_rgb, radius, frequency) tuples.

### LabelingAgent
Procedural name generation with 20+ vocabulary sets. Each set has themed prefix, suffix, and settlement name lists. Can use Claude API for richer lore generation.

### RendererAgent
Composites all layers into a final PNG: terrain colors, road markings, structure outlines, labels (3 font sizes by category), compass rose, legend, and decorative border.

## Unity Export Pipeline

Four specialized exporters run after the render step:

### UnityTerrainExporter
- `heightmap.raw` — 16-bit RAW heightmap
- `heightmap.png` — Visual preview
- `splatmap_0.png` — RGBA splat texture
- `water_mask.png`, `walkability_mask.png`
- `terrain_config.json` — TerrainLayer definitions per biome

### UnitySceneExporter
- `.unity` YAML scene file with directional light (biome-tuned), camera, terrain object, water plane, and structure GameObjects
- Prefab manifest mapping entity types to Unity prefab paths

### UnityCSharpExporter
5 C# MonoBehaviour scripts:
- `MapLoader.cs` — Main entry point with data classes
- `MapConfig.cs` — ScriptableObject for map configuration
- `TerrainBuilder.cs` — RAW heightmap + splatmap import
- `EntitySpawner.cs` — Prefab spawning with terrain snap
- `WaterController.cs` — Water planes + river LineRenderers
- `MapData.json` — Full serialized map state

### UnityTilemapExporter
For 2D top-down views or minimap overlays:
- `tilemap_data.json` — Tile index grid
- `tile_palette.png` — Sprite sheet
- `tilemap_preview.png` — Visual preview
- `collision_map.json` — Walkability data
- `TilemapLoader.cs` — Runtime loader script

## Data Flow

```
Goal (natural language)
  |
  v
StrategicPlanner.plan()
  |  - Tries Claude API (creative DAG generation)
  |  - Falls back to DAG_TEMPLATES dictionary
  v
TaskDAG (validated, topologically sorted)
  |
  v
SharedState (initialized with MapConfig)
  |
  v
Orchestrator.execute_dag()
  |  - Level 0: TerrainAgent writes elevation, moisture, terrain_color
  |  - Level 1: WaterAgent writes water_mask, updates terrain_color
  |  - Level 2: PathfindingAgent writes paths list
  |  - Level 3: StructureAgent writes structure_mask, entities list
  |  - Level 4: AssetAgent writes additional entities
  |  - Level 5: LabelingAgent writes labels list
  |  - Level 6: RendererAgent composites final image
  |  - Level 7: Unity exporters read full state, write export files
  v
Output files (PNG map + Unity assets)
```

## SharedState Data Layers

| Layer | Type | Description |
|-------|------|-------------|
| elevation | float32 numpy array | Height values 0.0-1.0 |
| moisture | float32 numpy array | Moisture values 0.0-1.0 |
| walkability | bool numpy array | True = passable terrain |
| water_mask | bool numpy array | True = water present |
| structure_mask | bool numpy array | True = structure present |
| terrain_color | uint8 numpy array (H,W,3) | RGB color per pixel |
| entities | list[Entity] | Buildings, objects, POIs |
| paths | list[PathSegment] | Roads, rivers, streams |
| labels | list[Label] | Text labels and names |

## Claude API Integration

When an Anthropic API key is set, the system uses Claude for:

1. **Creative DAG planning** — Generates custom task graphs from natural language goals
2. **Lore-rich labeling** — Produces thematic names, descriptions, and backstory
3. **Fallback** — Everything works without an API key using templates and procedural generation

Model: `claude-sonnet-4-20250514`

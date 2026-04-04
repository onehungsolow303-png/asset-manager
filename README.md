# Map Generator

A 3-tier multi-agent procedural map generation system for Unity, powered by Anthropic's Claude API.

Generates 30 map types including dungeons, castles, cities, temples, graveyards, docks, factories, and open world maps with full Unity export support.

## Quick Start

### 1. Install Dependencies

```bash
cd "Map Generator"
pip install -r requirements.txt
```

### 2. Set Your API Key (Optional)

The system works without an API key using template-based planning. For Claude-powered creative planning and richer labeling, set your key:

```bash
# Windows (Command Prompt)
set ANTHROPIC_API_KEY=sk-ant-your-key-here

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY="sk-ant-your-key-here"

# Mac/Linux
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 3. Generate a Map

```python
from mapgen_agents.map_generator import MapGenerator

gen = MapGenerator(api_key="sk-ant-...", verbose=True)  # or api_key=None for templates

result = gen.generate(
    goal="A haunted graveyard shrouded in mist",
    map_type="graveyard",
    biome="forest",
    size="standard",       # 512x512
    seed=42,
    unity_export=True,
    output_dir="./output"
)
```

### 4. Run the Demo

```bash
cd mapgen_agents
python demo.py
```

### 5. Run All Tests

```bash
cd mapgen_agents
python test_all_types.py
```

## Supported Map Types (30)

**Settlements:** village, town, city
**Fortifications:** castle, fort, tower
**Underground/Interior:** dungeon, cave, mine, maze, treasure_room
**Religious/Burial:** crypt, tomb, graveyard, temple, church
**Commercial/Industrial:** shop, shopping_center, factory
**Waterfront:** dock
**Combat:** arena
**Field/Outdoor:** wilderness, camp, outpost, rest_area, crash_site
**Large Scale:** biomes, region, open_world, world_box

## Water Features (5)

rivers, streams, ponds, lakes, oceans

## Biomes (9)

forest, mountain, desert, swamp, plains, tundra, volcanic, cave, dungeon

## Size Presets

| Preset | Resolution |
|--------|-----------|
| small_encounter | 256x256 |
| medium_encounter | 512x512 |
| large_encounter | 768x768 |
| standard | 512x512 |
| large | 1024x1024 |
| region | 1024x1024 |
| open_world | 1536x1536 |

## Unity Export

When `unity_export=True`, the system generates:

- **Terrain data:** 16-bit RAW heightmap, splatmaps, water/walkability masks
- **Scene file:** .unity YAML with lights, camera, terrain, water, structures
- **C# scripts:** MapLoader, TerrainBuilder, EntitySpawner, WaterController
- **Tilemap data:** 2D tile grid, palette sprite sheet, collision map, TilemapLoader.cs
- **JSON data:** Full map state for runtime loading

## Using with Claude Code

```bash
cd "Map Generator"
claude
```

Then ask Claude to generate maps, modify agents, add new map types, or debug issues directly in the codebase.

## Project Structure

```
Map Generator/
  requirements.txt
  ARCHITECTURE.md
  README.md
  mapgen_agents/
    __init__.py
    map_generator.py      # Top-level API
    planner.py            # Tier 1 - Strategic planning + DAG templates
    orchestrator.py       # Tier 2 - Task dispatch + retry logic
    dag_engine.py         # DAG data structure + validation
    base_agent.py         # Abstract agent base class
    shared_state.py       # Central data layer (numpy arrays + dataclasses)
    llm_adapter.py        # Claude API adapter + prompts
    demo.py               # Quick demo script
    test_all_types.py     # Full test suite (30 map types)
    agents/
      __init__.py
      terrain_agent.py          # Perlin noise terrain + biome presets
      water_agent.py            # Rivers, streams, ponds, lakes, oceans
      pathfinding_agent.py      # A* roads + MST network
      structure_agent.py        # 23 structure types (BSP, maze, tunnels, etc.)
      asset_agent.py            # Poisson disk asset placement
      labeling_agent.py         # Procedural name generation
      renderer_agent.py         # Final PNG compositing
      unity_terrain_exporter.py # Heightmaps + splatmaps
      unity_scene_exporter.py   # .unity YAML scenes
      unity_csharp_exporter.py  # C# MonoBehaviour scripts
      unity_tilemap_exporter.py # 2D tilemap data + loader
```

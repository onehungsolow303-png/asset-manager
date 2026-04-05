# Generation Overhaul Design Spec

**Date:** 2026-04-04
**Status:** Approved
**Scope:** Complete rewrite of the map generation pipeline — all 30 map types

## Overview

Replace the current single-pass, BSP-based generation system with a three-phase, pipeline-coordinated architecture. Noise-based terrain feeds topology-driven room layout which feeds D&D-style encounter, trap, and loot population. All generation is purely algorithmic (no LLM dependency), deterministic given a seed, with narrative hooks stubbed for future Claude API enrichment.

### Design Goals

- **Noise-based terrain:** Perlin noise for elevation/moisture, cellular automata for cave smoothing, natural-feeling geology
- **Multi-pass pipeline:** Three phases (Terrain, Layout, Population) with validation gates and retry logic
- **Non-linear layouts:** Four topology types (linear, loop, hub-and-spoke, hybrid) selected per map type and size
- **Intelligent placement:** Budget-driven encounters with pacing curves, danger-mapped traps, risk-reward loot, purpose-matched dressing
- **Data-driven map types:** 30 types expressed as profile dicts, grouped into 6 families. No per-type code — only data.

### What This Replaces

- Hardcoded DAG templates in `planner.py` (for generation; planner retained for Claude-API creative mode)
- `BUILDING_TEMPLATES` in `structure_agent.py` (replaced by profile room pools + TopologyAgent)
- `MAP_TYPE_ENEMIES` in `spawn_agent.py` (replaced by profile creature tables + EncounterAgent)
- BSP-only room placement in StructureAgent (replaced by topology-graph-driven placement)

---

## 1. Pipeline Coordinator & Phase Architecture

### PipelineCoordinator

New top-level class that orchestrates generation. Receives a `GenerationRequest` and manages three phases:

```python
@dataclass
class GenerationRequest:
    map_type: str           # one of 30 types
    biome: str              # one of 12 biomes
    size: str               # small_encounter, medium_encounter, large_encounter, standard, large, region, open_world
    seed: int
    party_level: int        # 1-20, for encounter/loot budget calculation
    party_size: int         # typically 3-6
    output_dir: str
    unity_export: bool
```

Coordinator flow:

1. Load profile for `map_type`
2. Resolve family from profile
3. Run Phase 1 (Terrain) — validate — retry up to 3x on failure
4. Run Phase 2 (Layout) — validate — retry up to 3x (reuses Phase 1 output)
5. Run Phase 3 (Population) — validate — retry up to 3x (reuses Phase 2 output)
6. Run output agents (RendererAgent, Unity Exporters)

Retry logic: on validation failure, the coordinator adjusts params (relaxed thresholds, reduced room count, wider corridors) and re-runs only the failed phase. After 3 failures, falls back to relaxed constraints that guarantee completion.

### Phase 1 — Terrain (Geology)

Agents: TerrainAgent, WaterAgent, CaveCarverAgent

**Produces:** elevation grid, moisture grid, biome classification, water mask, cave_mask, natural_openings list

**Validation:**
- Walkable area >= minimum for map size (configurable per family)
- Water doesn't partition the map into disconnected landmasses
- Biome coverage matches expectations (e.g., dungeon biome should be mostly rock)

### Phase 2 — Layout (Architecture)

Agents: TopologyAgent, StructureAgent (enhanced), ConnectorAgent, PathfindingAgent (enhanced)

**Produces:** RoomGraph realized in physical space — rooms carved into terrain, corridors connecting them, doors/stairs placed, zone boundaries set

**Validation:**
- All rooms reachable from entrance
- Entrance-to-boss path exists
- Zone count matches topology intent
- No orphaned corridors (every corridor connects two rooms)
- Room sizes within profile bounds

### Phase 3 — Population (Content)

Agents: RoomPurposeAgent, EncounterAgent, TrapAgent, LootAgent, DressingAgent, LabelingAgent, SpawnAgent (enhanced)

**Produces:** fully populated dungeon — creatures, traps, loot, furniture, names, spawn points

**Validation:**
- XP budget within +/-10% of target
- Loot budget within +/-15% of target
- Every purpose-assigned room has appropriate dressing (no empty rooms)
- Boss room has encounter + loot
- Entrance has player spawn

---

## 2. Map Type Families

Six families define which pipeline passes run and how. Each family configures phase behavior:

| Family | Map Types | Phase 1 | Phase 2 | Phase 3 |
|--------|-----------|---------|---------|---------|
| **Underground** | dungeon, cave, mine, maze, crypt, tomb | Dungeon noise, CaveCarver active | Carve-from-solid, topology rooms, rock corridors | Full D&D: encounters, traps, loot, dressing |
| **Fortification** | castle, fort, tower, outpost | Outdoor terrain, optional moat | Perimeter walls first, courtyard, rooms within | Guards-heavy, armory loot, defensive traps |
| **Settlement** | village, town, city, camp, rest_area | Outdoor terrain, roads | Roads first, buildings along roads, open spaces | NPCs-heavy, shops with inventory, civilian dressing |
| **Interior** | tavern, prison, library, throne_room, shop, shopping_center, factory, temple, church, treasure_room | Flat floor, no caves | Single-building floor plan, room adjacency, doors not corridors | Purpose-matched per type |
| **Outdoor** | wilderness, graveyard, dock, arena, crash_site | Full terrain + biome features | POI scattering (Poisson disk), natural paths | Sparse encounters, environmental hazards |
| **Large-scale** | biomes, region, open_world, world_box | Multi-biome tiling, region noise | Zone boundaries, settlement placement, road networks | Zone-level encounter tables, landmark dressing |

---

## 3. Map Type Profiles

Each of the 30 map types is a data-driven profile dict. No code per type — only data.

### Profile Schema

```python
{
    "family": str,                          # one of 6 families
    "topology_preference": list[str],       # ordered preference: linear_with_branches, loop_based, hub_and_spoke, hybrid
    "size_topology_override": dict[str, str], # size preset -> forced topology
    "room_pool": {
        "required": list[str],              # must appear (entrance, boss_lair, etc.)
        "common": list[str],                # 60% of remaining rooms
        "uncommon": list[str],              # 30% of remaining rooms
        "rare": list[str],                  # 10% of remaining rooms
    },
    "creature_table": {
        "common": list[tuple[str, int]],    # (creature_type, weight)
        "uncommon": list[tuple[str, int]],
        "boss": list[tuple[str, int]],
    },
    "trap_density": float,                  # 0.0-1.0, fraction of rooms with traps
    "loot_tier": str,                       # low, medium, high, legendary
    "dressing_palette": str,                # key into DRESSING_PALETTES
    "biome_override": str | None,           # force biome or use requested
    "z_levels": {"min": int, "max": int},   # vertical extent
    "corridor_style": str,                  # carved, built, natural, road, hallway
    "door_frequency": float,                # 0.0-1.0, fraction of connections with doors
    "secret_room_chance": float,            # 0.0-1.0, chance per eligible wall
}
```

### Sample Profiles

**dungeon (Underground):**
```python
{
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
}
```

**village (Settlement):**
```python
{
    "family": "settlement",
    "topology_preference": ["hub_and_spoke"],
    "size_topology_override": {"small_encounter": "linear_with_branches"},
    "room_pool": {
        "required": ["entrance", "town_square"],
        "common": ["house", "tavern", "shop", "farm", "well"],
        "uncommon": ["blacksmith", "temple", "inn", "stable"],
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
}
```

**tavern (Interior):**
```python
{
    "family": "interior",
    "topology_preference": ["linear_with_branches"],
    "size_topology_override": {},
    "room_pool": {
        "required": ["entrance", "common_room"],
        "common": ["kitchen", "bar", "guest_room", "storage"],
        "uncommon": ["cellar", "owner_quarters", "stable"],
        "rare": ["secret_room", "gambling_den"],
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
}
```

Remaining 27 profiles follow the same schema. Each is pure data.

---

## 4. Topology Engine (TopologyAgent)

New agent that generates an abstract room graph before any spatial placement.

### Input
- Map type profile (topology preference, size overrides)
- Map size preset
- Seed
- Room count estimate (from profile room pool sizes)

### Output
- `RoomGraph`: nodes (room slots with zone ID) and edges (connections with type annotations)

### Topology Types

**Linear with Branches:**
Main path from entrance to boss with side branches for optional content. Entrance at one end, boss at the other. Branches contain treasure rooms, secrets, dead ends.
- Triggers: small_encounter size, mine, maze types

**Loop-Based:**
Rooms form cycles with multiple routes. Shortcuts (one-way doors, pit traps, locked doors opened from one side) create asymmetric traversal.
- Triggers: large size, dungeon, castle, fort types

**Hub-and-Spoke:**
Central hub room connects to 3-5 themed wings. Each wing is a mini-dungeon with its own rooms and mini-boss. Boss wing is the most difficult.
- Triggers: medium/standard size, dungeon, temple, castle types

**Hybrid (Hub + Loops):**
Hub provides orientation; wings contain internal loops and shortcuts. Most complex topology.
- Triggers: large/open_world size, or explicit hybrid profile preference

### Generation Algorithm

1. Select topology type from profile preference list (size can override)
2. Generate base graph:
   - Linear: chain of N nodes + random branch attachments
   - Loop: spanning tree + cycle-creating back-edges (1 cycle per 4-5 rooms)
   - Hub: star graph with wing sub-chains
   - Hybrid: star graph with loop-bearing wing sub-graphs
3. Assign zone IDs: BFS from entrance, zones increment every K rooms (K = total_rooms / desired_zones)
4. Tag special nodes:
   - Entrance: always zone 0, degree >= 1
   - Boss: always deepest zone, degree 1 or 2
   - Treasure rooms: placed on branches or dead ends, mid-to-deep zones
5. Insert optional edges:
   - Shortcuts: one-way connections skipping 2-3 rooms (loop/hybrid only)
   - Secret passages: connect non-adjacent rooms through walls
   - Locked doors: require key from another room (creates key-gate puzzle)
6. Annotate edges with connection type: corridor, door, locked_door, secret, one_way, stairs

### Zone System

Zones represent difficulty tiers. Zone assignment:
- Zone 0: entrance area (1-2 rooms)
- Zone 1-2: outer rooms (easy encounters, light loot)
- Zone 3-4: middle rooms (moderate encounters, traps appear)
- Zone 5+: inner/boss rooms (hard encounters, best loot, most traps)

Zone count scales with room count: roughly 1 zone per 3-4 rooms.

---

## 5. CaveCarverAgent

New Phase 1 agent. Takes TerrainAgent noise maps and carves natural cavities.

### Algorithm

1. **Primary noise layer:** elevation from TerrainAgent. Tiles below `carve_threshold` become open space.
2. **Secondary noise layer:** second noise pass at different frequency. Where both layers agree on "open" = large caverns. Where only one agrees = narrow passages. Neither = solid rock.

```python
cave_mask = (elevation < carve_threshold) & (secondary_noise < passage_threshold)
```

3. **Cellular automata smoothing:** 2-3 iterations of B678/S345678 rule. Smooths ragged noise edges into natural cave walls.
4. **Flood fill validation:** find largest connected region. Fill isolated pockets (< 15 tiles) back to solid. Guarantees one connected cave system.

### Family-Specific Parameters

| Family | carve_threshold | passage_threshold | Smoothing Iterations | Active |
|--------|----------------|-------------------|---------------------|--------|
| Underground | 0.45 | 0.50 | 3 | Yes |
| Fortification | — | — | — | No (skipped) |
| Settlement | — | — | — | No (skipped) |
| Interior | — | — | — | No (skipped) |
| Outdoor | 0.35 | 0.40 | 2 | Yes (light) |
| Large-scale | 0.40 | 0.45 | 2 | Yes |

### Output

- `cave_mask`: boolean grid (True = open space)
- `natural_openings`: list of (x, y, approximate_width, approximate_height) for large cavern centers

### Interaction with Phase 2

- **Underground:** StructureAgent places rooms within natural openings where possible. Corridors follow existing passages. Result: dungeon built into natural cave system.
- **Outdoor:** cave openings become POIs (cave entrances, cliff shelters) for topology graph.

### Biome-Specific Features

| Biome | Tagged Features |
|-------|----------------|
| cave | stalagmites, underground_pool, crystal_formation |
| dungeon | rough_hewn_wall (man-made edges on natural caves) |
| volcanic | lava_tube, obsidian_flow, vent_shaft |
| swamp | sinkhole, mud_cavern, root_tunnel |
| mountain | crevasse, ore_vein, ice_cave |

Features stored as entities for DressingAgent reference.

---

## 6. ConnectorAgent

New Phase 2 agent. Creates corridors, doors, and vertical transitions.

### Corridor Generation

For each edge in the RoomGraph:
1. Find closest wall tiles between the two rooms
2. Carve corridor using A* pathfinding through solid rock (preferring existing cave passages when available)
3. Corridor width from profile's `corridor_style`:
   - `carved`: 2-3 tiles wide, rough edges
   - `built`: 3-4 tiles wide, straight walls
   - `natural`: variable width following cave contours
   - `road`: 4-6 tiles wide, outdoor paths
   - `hallway`: 2 tiles wide, straight, interior

### Door Placement

For edges annotated as `door`:
- Place door entity at corridor-room boundary
- Door type: wooden (default), iron (fortification), locked (locked_door edge), secret (secret edge — hidden wall section)
- Frequency controlled by `profile.door_frequency`

### Vertical Transitions

For multi-z-level dungeons:
- Stairs placed at edges annotated as `stairs`
- Position: room corner or corridor junction
- Types: stairs_up, stairs_down, ladder, trapdoor, pit (one-way down)
- Each transition creates corresponding entry point on the target z-level

### Secret Passages

For edges annotated as `secret`:
- Carved as narrow (1-tile) corridors through walls
- Entrance disguised as wall tile (revealed by interaction in viewer)
- Connect non-adjacent rooms, often linking outer zone to deep treasure

---

## 7. Encounter & Difficulty System (EncounterAgent)

New Phase 3 agent. Distributes XP budget across rooms using a pacing curve.

### Budget Calculation

```
base_xp = PARTY_XP_TABLE[party_level] * party_size
difficulty_mult = {"low": 0.6, "medium": 1.0, "high": 1.5, "legendary": 2.0}[profile.loot_tier]
total_xp_budget = base_xp * difficulty_mult * room_count_factor
```

`PARTY_XP_TABLE` follows D&D 5e encounter XP thresholds per level. `difficulty_mult` is derived from `loot_tier` — higher loot tiers imply higher-danger dungeons that justify the rewards. `room_count_factor` scales sub-linearly (sqrt(room_count) / sqrt(8)) to prevent absurd totals in large dungeons.

### Room Count Determination

The number of rooms is calculated from map size and family:

```
SIZE_ROOM_COUNTS = {
    "small_encounter":  {"underground": 5,  "fortification": 4,  "settlement": 4,  "interior": 4,  "outdoor": 3,  "large_scale": 6},
    "medium_encounter": {"underground": 8,  "fortification": 6,  "settlement": 6,  "interior": 6,  "outdoor": 5,  "large_scale": 10},
    "large_encounter":  {"underground": 12, "fortification": 8,  "settlement": 8,  "interior": 8,  "outdoor": 7,  "large_scale": 15},
    "standard":         {"underground": 10, "fortification": 8,  "settlement": 8,  "interior": 7,  "outdoor": 6,  "large_scale": 12},
    "large":            {"underground": 16, "fortification": 12, "settlement": 12, "interior": 10, "outdoor": 10, "large_scale": 20},
    "region":           {"underground": 20, "fortification": 15, "settlement": 15, "interior": 12, "outdoor": 12, "large_scale": 30},
    "open_world":       {"underground": 25, "fortification": 20, "settlement": 20, "interior": 15, "outdoor": 15, "large_scale": 50},
}
```

The base count is then jittered by +/-20% (seeded) for variety. Required rooms from the profile always fit within this count.

### Pacing Curve

Budget distributed across rooms ordered by graph distance from entrance:

1. **Base ramp:** linear increase from 5% of per-room average at entrance to 100% at mid-dungeon
2. **Climax spike:** boss room gets 20-30% of total budget
3. **Treasure spikes:** treasure_vault and guarded rooms get 1.5-2x the base ramp value

```
room_xp = base_ramp(position) * zone_multiplier * room_purpose.encounter_mult * spike_modifier
```

**Empty rooms:** 15-25% of rooms intentionally get 0 XP allocation. These become rest points, puzzle rooms, or atmospheric dressing. Placed to create pacing rhythm.

### Creature Selection Per Room

1. Look up room's zone -> zone CR range
2. Pull candidates from profile's `creature_table` matching CR range
3. Build encounter group:
   - Start with strongest creature that fits remaining XP
   - Fill remaining XP with smaller creatures
   - Respect room size: large rooms (> 60 tiles) get more creatures, small rooms (< 20 tiles) get fewer but tougher
4. Boss rooms: pull from `boss` creature list, add minions from `common` list with remaining budget

### Adjacency Awareness

- Guard rooms adjacent to treasure vaults: +25% XP budget
- Rooms adjacent to entrance: weaker encounters (warm-up)
- Dead-end branch rooms: can be empty or trap-only (exploration reward without forced combat)

---

## 8. Trap System (TrapAgent)

New Phase 3 agent. Places traps based on a danger map.

### Danger Map

Each room gets a danger score (0.0-1.0):
- Base: zone depth normalized (outer=0.1, inner=0.5, boss_approach=0.8)
- +0.2 if room guards treasure vault or boss path
- +0.15 if room is on shortcut/secret passage
- -0.3 if room is entrance, safe_haven, or rest point
- Clamped to [0.0, 1.0]

### Placement Rules

1. Roll against `profile.trap_density` per room
2. Rooms with danger > 0.6 get priority placement regardless of roll
3. Trap type from weighted family table:

| Family | Common | Uncommon | Rare |
|--------|--------|----------|------|
| Underground | pit, spike_floor, dart_wall | poison_gas, collapsing_ceiling | boulder, teleport |
| Fortification | arrow_slit, portcullis, murder_hole | boiling_oil, alarm | drawbridge_drop |
| Interior | locked_door, tripwire, false_floor | poison_needle, swinging_blade | mimic |
| Outdoor | snare, quicksand, camouflaged_pit | rockslide, beehive | — |

4. Difficulty scales with zone: damage dice and save DC increase with depth
5. Spatial placement:
   - Corridor traps: midpoints
   - Room traps: entrances or near treasure
   - Secret passage traps: passage entrance

### Trap-Encounter Interaction

- Traps in encounter rooms: environmental hazard during combat (encounter multiplier)
- Traps in empty rooms: standalone skill challenges
- Trapped rooms adjacent to combat: tactical retreat penalty

---

## 9. Loot Economy (LootAgent)

New Phase 3 agent. Budget pool with risk-reward distribution.

### Budget Calculation

```
base_gold = TREASURE_TABLE[party_level] * party_size
tier_mult = {"low": 0.5, "medium": 1.0, "high": 1.5, "legendary": 2.5}
total_loot_budget = base_gold * tier_mult[profile.loot_tier]
```

### Three Pools

| Pool | % of Budget | Distribution |
|------|-------------|-------------|
| Main | 60% | Across rooms proportional to risk-reward score |
| Boss | 25% | Reserved for boss room — guaranteed quality drop |
| Exploration bonus | 15% | Secret rooms, hidden caches, dead-end rewards |

### Risk-Reward Score

```
risk_score = (encounter_xp / max_encounter_xp) * 0.5 + danger_score * 0.3 + depth_factor * 0.2
```

Main pool distributed proportionally to risk_score.

### Loot Type by Room Purpose

| Room Purpose | Loot Bias |
|-------------|-----------|
| treasure_vault | Gold, gems, art objects, magic items (rare) |
| armory | Weapons, armor, shields, magic weapons (rare) |
| alchemy_lab | Potions, reagents, scrolls |
| library | Scrolls, spellbooks, maps |
| shrine/temple | Holy items, blessed gear, relics |
| crypt/tomb | Ancient weapons, cursed items, burial goods |
| boss_lair | Best single item + gold hoard |
| generic | Mixed — coins, minor consumables |

### Item Rarity Curve

- **Outer zones (0-1):** 70% mundane, 30% common magic
- **Middle zones (2-3):** 50% common, 40% uncommon, 10% rare
- **Inner/boss zones (4+):** 20% uncommon, 50% rare, 25% very rare, 5% legendary

Boss pool always contains at least one item one rarity tier above the dungeon's normal ceiling.

### Exploration Bonus

Secret/optional rooms draw from the bonus pool. Deliberately better per-room than main-path loot. A secret room in the outer zone may contain uncommon-tier loot normally gated to middle zones.

---

## 10. Dressing & Atmosphere (DressingAgent)

New Phase 3 agent. Fills rooms with non-mechanical content.

### Dressing Palettes

Each profile specifies a `dressing_palette` key into the palette registry:

```python
DRESSING_PALETTES = {
    "dungeon": {
        "universal": ["torch", "cobweb", "rubble", "bones", "chains"],
        "by_purpose": {
            "guard_room": ["weapon_rack", "table", "chair", "lantern", "barrel"],
            "barracks": ["bunk_bed", "footlocker", "armor_stand", "chamber_pot"],
            "armory": ["weapon_rack", "shield_display", "grindstone", "crate"],
            "storage": ["barrel", "crate", "sack", "shelf", "broken_pottery"],
            "alchemy_lab": ["cauldron", "bookshelf", "potion_shelf", "brazier", "herb_rack"],
            "library": ["bookshelf", "desk", "candelabra", "scroll_rack", "reading_chair"],
            "shrine": ["altar", "candles", "statue", "offering_bowl", "prayer_mat"],
            "crypt": ["sarcophagus", "coffin", "urn", "memorial_plaque", "eternal_flame"],
            "boss_lair": ["throne", "trophy_pile", "banner", "brazier", "cage"],
            "treasure_vault": ["chest", "gold_pile", "gem_display", "pedestal", "locked_case"],
            "cell": ["shackles", "straw_pile", "bucket", "scratched_wall"],
            "entrance": ["gate", "murder_holes", "portcullis_track", "guard_alcove"],
        },
        "corridor": ["torch", "cobweb", "crack", "puddle", "rat_bones"],
    },
    # Additional palettes: settlement, tavern, fortification, outdoor, etc.
}
```

### Placement Rules

1. **Universal items:** 1-3 per room, random valid floor tiles
2. **Purpose items:** 2-5 per room from purpose-specific list:
   - Wall-mounted (torch, weapon_rack, shelf) -> adjacent to walls
   - Center (table, altar, throne) -> room center area
   - Corner (chest, barrel, crate) -> within 2 tiles of corners
   - Entrance (gate, portcullis) -> at room doorways
3. **Corridor items:** 1 per 8-12 corridor tiles, sparse
4. **Room size scaling:** small (< 20 tiles) 2-3 items, medium (20-60) 4-6, large (> 60) 6-10
5. **No overlap:** items cannot share tiles with entities, spawns, traps, or doors

### Atmospheric Metadata

Each room purpose has atmosphere tags stored in room metadata:

```python
ATMOSPHERE = {
    "guard_room": {"lighting": "torchlit", "sound": "armor_clink"},
    "crypt": {"lighting": "dim", "sound": "dripping"},
    "alchemy_lab": {"lighting": "green_glow", "sound": "bubbling"},
    "boss_lair": {"lighting": "dramatic", "sound": "ominous_hum"},
    "library": {"lighting": "candlelit", "sound": "page_rustle"},
    "shrine": {"lighting": "warm_glow", "sound": "chanting"},
    "cell": {"lighting": "dark", "sound": "chains_rattle"},
    "treasure_vault": {"lighting": "glittering", "sound": "silence"},
}
```

Viewer's existing theme tinting system reads lighting tags. Sound tags are hooks for future audio.

---

## 11. Room Purpose System (RoomPurposeAgent)

New Phase 3 agent. Assigns each room a role from the profile's room pool.

### Room Purpose Definitions

Each purpose has gameplay multipliers used by EncounterAgent, TrapAgent, and LootAgent:

```python
ROOM_PURPOSES = {
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
}
```

### Adjacency Preferences

Soft constraints per family. RoomPurposeAgent scores candidate assignments and picks best:

```python
ADJACENCY_RULES = {
    "underground": {
        "guard_room":     {"near": ["entrance", "treasure_vault", "boss_lair"], "far": ["safe_haven"]},
        "barracks":       {"near": ["armory", "guard_room", "storage"],         "far": ["boss_lair"]},
        "treasure_vault": {"near": ["guard_room"],                              "far": ["entrance"]},
        "boss_lair":      {"near": ["treasure_vault"],                          "far": ["entrance", "safe_haven"]},
        "safe_haven":     {"near": ["entrance"],                                "far": ["boss_lair", "guard_room"]},
        "alchemy_lab":    {"near": ["library", "storage"],                      "far": []},
        "library":        {"near": ["alchemy_lab", "shrine"],                   "far": []},
        "shrine":         {"near": ["crypt", "library"],                        "far": ["barracks"]},
    },
    # Similar tables for fortification, settlement, interior, outdoor, large_scale
}
```

### Assignment Algorithm

1. Place required rooms first (entrance at zone 0 entrance node, boss_lair at deepest zone boss node)
2. For each remaining room node, score every eligible purpose from the pool:
   - +10 if adjacent to a "near" room
   - -10 if adjacent to a "far" room
   - +5 if zone matches purpose expectation (combat rooms in mid-deep zones, utility in outer-mid)
   - Random jitter (+/-3) for variety
3. Select highest-scoring purpose, remove from available pool if it has a max count
4. Rooms with no strong preference get "storage" or "cell" (generic filler)

---

## 12. New & Enhanced Agents Summary

### New Agents (9)

| Agent | Phase | Responsibility |
|-------|-------|---------------|
| PipelineCoordinator | Orchestration | 3-phase flow, validation gates, retry, profile loading |
| CaveCarverAgent | 1 - Terrain | Noise-threshold carving + cellular automata + flood fill |
| TopologyAgent | 2 - Layout | Abstract room graph (4 topology types), zone assignment |
| ConnectorAgent | 2 - Layout | Corridors, doors, stairs, secret passages |
| RoomPurposeAgent | 3 - Population | Room role assignment from profile with adjacency scoring |
| EncounterAgent | 3 - Population | XP budget distribution, pacing curve, creature selection |
| TrapAgent | 3 - Population | Danger map, trap placement + type + difficulty scaling |
| LootAgent | 3 - Population | Three-pool budget, risk-reward, item rarity curve |
| DressingAgent | 3 - Population | Purpose-matched furniture, atmosphere tags, spatial placement |

### Enhanced Agents (4)

| Agent | Changes |
|-------|---------|
| TerrainAgent | New presets for non-noise families (flat floor, road-ready). Expose noise layers for CaveCarver. |
| StructureAgent | Accept RoomGraph from TopologyAgent. Place rooms into cave openings. Room sizing from profiles. |
| PathfindingAgent | Validation mode: verify connectivity against topology graph. Report orphans and broken edges. |
| SpawnAgent | Read placements from EncounterAgent. Player spawn from topology entrance node. |

### Unchanged Agents (6)

| Agent | Reason |
|-------|--------|
| WaterAgent | Already handles all water types needed |
| AssetAgent | Still used for outdoor biome scatter; DressingAgent handles interiors |
| LabelingAgent | Works as-is; narrative hooks already stubbed |
| RendererAgent | Reads SharedState agnostically |
| Unity Exporters (4) | Read SharedState agnostically |

### Deprecated

- `MAP_TYPE_ENEMIES` dict in spawn_agent.py
- `BUILDING_TEMPLATES` dict in structure_agent.py
- Hardcoded DAG templates in planner.py (planner retained for Claude-API creative mode)

---

## 13. Data Flow Summary

```
GenerationRequest
  -> PipelineCoordinator
    -> loads profile for map_type
    -> resolves family

    Phase 1 — Terrain:
      TerrainAgent -> elevation, moisture, biome grid
      WaterAgent -> rivers, lakes, water mask
      CaveCarverAgent -> cave_mask, natural_openings
      [Terrain Validation]

    Phase 2 — Layout:
      TopologyAgent -> RoomGraph (abstract nodes + edges + zones)
      StructureAgent -> rooms placed in physical space
      ConnectorAgent -> corridors, doors, stairs carved
      PathfindingAgent -> connectivity verified
      [Layout Validation]

    Phase 3 — Population:
      RoomPurposeAgent -> each room assigned a role
      EncounterAgent -> creatures placed per XP budget + pacing
      TrapAgent -> traps placed per danger map
      LootAgent -> treasure placed per loot budget + risk-reward
      DressingAgent -> furniture + atmosphere per purpose
      LabelingAgent -> names + descriptions
      SpawnAgent -> player + creature spawn points
      [Population Validation]

    Output:
      RendererAgent -> composite PNG
      Unity Exporters -> terrain, scene, C#, tilemap
```

---

## 14. Narrative Hooks (Future)

The system is designed for pure algorithmic generation now, with explicit hooks for future Claude API enrichment:

- **Room descriptions:** `room.metadata["description"]` field, currently empty. Future NarrativeAgent fills with Claude-generated prose.
- **Creature lore:** `spawn.metadata["lore"]` field. Future enrichment adds backstory, dialogue.
- **Quest hooks:** `room.metadata["quest_hook"]` field. Future agent generates mini-quests (fetch item from room X, defeat boss in room Y).
- **Dungeon history:** `shared_state.metadata["dungeon_lore"]` field. Future agent generates why this dungeon exists, who built it, what happened.
- **Item descriptions:** `loot.metadata["description"]` field. Future agent names magic items and writes flavor text.

These fields exist in the data model but are not populated by the algorithmic pipeline. A future `NarrativeAgent` in Phase 3 (after DressingAgent, before LabelingAgent) can fill them using Claude API calls.

---

## 15. Implementation Notes

### Data Tables to Complete During Implementation

This spec defines schemas and sample data for 3 of 30 profiles. The remaining 27 profiles, plus the following data tables, will be filled during implementation following the established schemas:

- **Map type profiles:** 27 remaining profiles (cave, mine, maze, crypt, tomb, castle, fort, tower, outpost, town, city, camp, rest_area, prison, library, throne_room, shop, shopping_center, factory, temple, church, wilderness, graveyard, dock, arena, crash_site, biomes, region, open_world, world_box)
- **Adjacency rules:** 5 remaining family tables (fortification, settlement, interior, outdoor, large_scale)
- **Dressing palettes:** 5 remaining palettes (settlement, tavern, fortification, outdoor, large_scale)
- **Trap tables:** settlement and large_scale families
- **PARTY_XP_TABLE:** D&D 5e encounter XP thresholds, levels 1-20
- **TREASURE_TABLE:** D&D 5e treasure hoard values, levels 1-20
- **Atmosphere tags:** remaining room purposes

All follow defined schemas — implementation is data entry, not design work.

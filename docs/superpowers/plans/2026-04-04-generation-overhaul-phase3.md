# Generation Overhaul Phase 3: Population Agents

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build Phase 3 population agents: RoomPurposeAgent, EncounterAgent, TrapAgent, LootAgent, DressingAgent, enhanced SpawnAgent, and wire into PipelineCoordinator.

**Architecture:** RoomPurposeAgent assigns roles to rooms from profile pool. EncounterAgent distributes XP budget with pacing curve. TrapAgent places traps from danger map. LootAgent distributes treasure via risk-reward. DressingAgent fills rooms with furniture. SpawnAgent reads EncounterAgent output. PipelineCoordinator orchestrates and validates.

**Tech Stack:** Python 3.11+, numpy, pytest

**Depends on:** Phase 1 + Phase 2 (complete)

---

## File Map

### New Files

| File | Responsibility |
|------|---------------|
| `mapgen_agents/agents/room_purpose_agent.py` | Assign room roles from profile with adjacency scoring |
| `mapgen_agents/agents/encounter_agent.py` | XP budget distribution, pacing curve, creature selection |
| `mapgen_agents/agents/trap_agent.py` | Danger map, trap placement + type selection |
| `mapgen_agents/agents/loot_agent.py` | Three-pool budget, risk-reward, item rarity |
| `mapgen_agents/agents/dressing_agent.py` | Purpose-matched furniture + atmosphere tags |
| `tests/test_room_purpose_agent.py` | Tests |
| `tests/test_encounter_agent.py` | Tests |
| `tests/test_trap_agent.py` | Tests |
| `tests/test_loot_agent.py` | Tests |
| `tests/test_dressing_agent.py` | Tests |
| `tests/test_phase3_integration.py` | End-to-end tests |

### Modified Files

| File | Changes |
|------|---------|
| `mapgen_agents/agents/spawn_agent.py` | Add mode to read from EncounterAgent output |
| `mapgen_agents/pipeline/coordinator.py` | Wire Phase 3 agents into `run_phase3()` |
| `mapgen_agents/pipeline/validation.py` | Implement `validate_population()` |

---

## Task 1: RoomPurposeAgent

**Files:** Create `mapgen_agents/agents/room_purpose_agent.py` + `tests/test_room_purpose_agent.py`

The agent assigns each room in the RoomGraph a purpose from the profile's room pool, respecting adjacency preferences.

**Tests:**
- Required rooms (entrance, boss_lair) are assigned first
- All rooms get a purpose (no None)
- Adjacency preferences are respected (guard_room near entrance scores higher)
- Room pool rarities are respected (rare rooms appear less)
- Deterministic with same seed

**Algorithm:**
1. Read room_graph and profile from params
2. Place required rooms: entrance purpose on entrance-tagged node, boss_lair on boss-tagged node
3. For remaining nodes, score every eligible purpose:
   - +10 if adjacent to a "near" room (from ADJACENCY_RULES)
   - -10 if adjacent to a "far" room
   - +5 if zone matches expectation (combat in mid-deep, utility in outer-mid)
   - Random jitter +/-3 from rng
4. Draw from pool by rarity: 60% common, 30% uncommon, 10% rare
5. Write purpose to each node: `node.purpose = "guard_room"`
6. Store room metadata in shared_state

Commit: `"feat: add RoomPurposeAgent with adjacency-scored purpose assignment"`

---

## Task 2: EncounterAgent

**Files:** Create `mapgen_agents/agents/encounter_agent.py` + `tests/test_encounter_agent.py`

Distributes XP budget across rooms using pacing curve.

**Tests:**
- Total XP distributed is within +/-20% of calculated budget
- Boss room gets highest XP allocation
- Entrance room gets low/zero XP
- 15-25% of rooms are empty (0 XP)
- Creature selection respects room size
- Deterministic with same seed

**Algorithm:**
1. Calculate total XP budget: `PARTY_XP_TABLE[party_level] * party_size * DIFFICULTY_MULT[loot_tier] * sqrt(room_count) / sqrt(8)`
2. Reserve boss_pool = 25% of budget
3. For each room ordered by graph distance from entrance:
   - Base allocation = linear ramp from 5% to 100% of per-room average
   - Multiply by room_purpose.encounter_mult
   - Guard rooms near treasure: +25%
   - 15-25% of rooms get 0 (empty, for pacing)
4. Boss room gets reserved pool
5. Select creatures from profile creature_table matching CR for each room
6. Write encounter data to room metadata: `node.metadata["encounter"] = {"creatures": [...], "xp": N}`

Commit: `"feat: add EncounterAgent with budget-driven pacing curve"`

---

## Task 3: TrapAgent

**Files:** Create `mapgen_agents/agents/trap_agent.py` + `tests/test_trap_agent.py`

Places traps based on danger map.

**Tests:**
- Trap count respects profile.trap_density
- High-danger rooms (>0.6) get priority traps
- Safe havens never get traps
- Trap difficulty scales with zone
- Deterministic

**Algorithm:**
1. Calculate danger score per room: base from zone depth + modifiers
2. For each room, roll against trap_density × room_purpose.trap_chance
3. Rooms with danger > 0.6 get traps regardless
4. Select trap type from family trap table (weighted by rarity)
5. Write trap data to room metadata

Commit: `"feat: add TrapAgent with danger-map-based trap placement"`

---

## Task 4: LootAgent

**Files:** Create `mapgen_agents/agents/loot_agent.py` + `tests/test_loot_agent.py`

Distributes treasure budget via risk-reward.

**Tests:**
- Total loot distributed within +/-25% of budget
- Boss room gets largest single allocation
- Secret/exploration rooms get bonus pool loot
- Treasure vaults get magic items
- Armories get magic weapons
- Item rarity scales with zone depth

**Algorithm:**
1. Calculate budget: `TREASURE_TABLE[party_level] * party_size * DIFFICULTY_MULT[loot_tier]`
2. Split into main (60%), boss (25%), exploration (15%) pools
3. Calculate risk_score per room: `encounter_xp * 0.5 + danger * 0.3 + depth * 0.2`
4. Distribute main pool proportionally to risk_score × room_purpose.loot_mult
5. Boss room gets boss pool
6. Secret/dead-end rooms get exploration pool
7. Convert gold to items based on room purpose loot bias + zone rarity curve
8. Write to room metadata

Commit: `"feat: add LootAgent with three-pool risk-reward distribution"`

---

## Task 5: DressingAgent

**Files:** Create `mapgen_agents/agents/dressing_agent.py` + `tests/test_dressing_agent.py`

Fills rooms with furniture and atmosphere.

**Tests:**
- Every room with a purpose gets dressing items
- Wall-mounted items are adjacent to walls
- Room size scaling (small rooms get fewer items)
- Items don't overlap with doors/traps
- Atmosphere tags are set
- Deterministic

**Algorithm:**
1. For each room node with a purpose:
   - Look up dressing palette from profile
   - Place 1-3 universal items on random floor tiles
   - Place 2-5 purpose-specific items with spatial logic (wall/center/corner)
   - Scale by room size
   - Set atmosphere metadata
2. For corridors: 1 item per 8-12 tiles
3. Write Entity objects to shared_state.entities

Commit: `"feat: add DressingAgent with purpose-matched furniture and atmosphere"`

---

## Task 6: SpawnAgent Enhancement + Phase 3 Integration

**Files:** Modify spawn_agent.py, coordinator.py, validation.py. Create test_phase3_integration.py.

**Tests (integration):**
- Full pipeline produces populated dungeon with encounters, traps, loot, dressing
- XP budget validation passes
- Every room has a purpose
- Player spawn exists at entrance
- Boss room has encounter + loot

**SpawnAgent changes:** When params.get("use_encounter_data") is True, read creature placements from room_graph node metadata instead of MAP_TYPE_ENEMIES. Place player spawn at entrance node position.

**Coordinator changes:** Wire all Phase 3 agents into run_phase3():
1. RoomPurposeAgent
2. EncounterAgent
3. TrapAgent
4. LootAgent
5. DressingAgent
6. LabelingAgent (existing, unchanged)
7. SpawnAgent (enhanced)
8. validate_population()

**Validation changes:** Implement validate_population() to check XP budget, loot budget, room purposes, player spawn.

Commit: `"feat: wire Phase 3 population agents into PipelineCoordinator"`

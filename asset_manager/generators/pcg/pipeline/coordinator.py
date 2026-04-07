"""PipelineCoordinator — Orchestrates 3-phase map generation with validation and retry.

Phase 1 (Terrain): TerrainAgent -> WaterAgent -> CaveCarverAgent
Phase 2 (Layout): TopologyAgent -> StructureAgent -> ConnectorAgent -> PathfindingAgent
Phase 3 (Population): Stub (implemented in Plan 3)
"""

import numpy as np
from shared_state import SharedState, MapConfig
from pipeline.generation_request import GenerationRequest
from pipeline.profiles import get_profile, FAMILIES
from pipeline.validation import (
    validate_terrain, validate_layout, validate_population, ValidationResult,
)
from agents.terrain_agent import TerrainAgent
from agents.water_agent import WaterAgent
from agents.cave_carver_agent import CaveCarverAgent
from agents.topology_agent import TopologyAgent
from agents.connector_agent import ConnectorAgent
from agents.structure_agent import StructureAgent
from agents.pathfinding_agent import PathfindingAgent
from agents.room_purpose_agent import RoomPurposeAgent
from agents.encounter_agent import EncounterAgent
from agents.trap_agent import TrapAgent
from agents.loot_agent import LootAgent
from agents.dressing_agent import DressingAgent
from agents.spawn_agent import SpawnAgent
from data.game_tables import SIZE_ROOM_COUNTS

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

    def __init__(self, request: GenerationRequest):
        self.request = request
        self.profile = get_profile(request.map_type)
        self.family = self.profile["family"]
        self.family_config = FAMILIES[self.family]

        biome_override = self.profile.get("biome_override")
        self.effective_biome = biome_override if biome_override else request.biome

        width, height = SIZE_DIMENSIONS[request.size]

        config = MapConfig(
            width=width,
            height=height,
            biome=self.effective_biome,
            map_type=request.map_type,
            seed=request.seed,
        )
        self.shared_state = SharedState(config)

    def generate(self) -> SharedState:
        # Phase 1: Terrain
        for attempt in range(MAX_RETRIES):
            result = self.run_phase1()
            if result.passed:
                break
            if attempt < MAX_RETRIES - 1:
                self.shared_state.metadata["terrain_retry"] = attempt + 1

        # Phase 2: Layout
        for attempt in range(MAX_RETRIES):
            result = self.run_phase2()
            if result.passed:
                break
            if attempt < MAX_RETRIES - 1:
                self.shared_state.metadata["layout_retry"] = attempt + 1

        # Phase 3: Population
        for attempt in range(MAX_RETRIES):
            result = self.run_phase3()
            if result.passed:
                break
            if attempt < MAX_RETRIES - 1:
                self.shared_state.metadata["population_retry"] = attempt + 1

        return self.shared_state

    def run_phase1(self) -> ValidationResult:
        state = self.shared_state

        # Determine terrain biome
        terrain_biome = self.effective_biome
        if self.family_config.get("terrain_preset") == "flat_floor":
            terrain_biome = "flat_floor"

        # TerrainAgent
        TerrainAgent().execute(state, {"biome": terrain_biome})

        # WaterAgent (skip for interior/underground families)
        if self.family not in ("interior", "underground"):
            WaterAgent().execute(state, {"biome": terrain_biome})

        # CaveCarverAgent
        if self.family_config.get("cave_carver", False):
            CaveCarverAgent().execute(state, {
                "carve_threshold": self.family_config.get("carve_threshold", 0.45),
                "passage_threshold": self.family_config.get("passage_threshold", 0.50),
                "smoothing_iterations": self.family_config.get("smoothing_iterations", 3),
            })
        else:
            CaveCarverAgent().execute(state, {"skip": True})

        min_walkable = 0.05 if self.family == "underground" else 0.2
        return validate_terrain(state, family=self.family, min_walkable_pct=min_walkable)

    def run_phase2(self) -> ValidationResult:
        """Execute Phase 2: Layout — topology, room placement, corridors, connectivity."""
        state = self.shared_state
        profile = self.profile
        rng = np.random.default_rng(self.request.seed + 100)

        # Calculate room count from size and family with +/-20% jitter
        base_count = SIZE_ROOM_COUNTS.get(self.request.size, {}).get(self.family, 8)
        jitter = rng.integers(-base_count // 5, base_count // 5 + 1)
        room_count = max(3, base_count + jitter)

        # TopologyAgent: generate abstract room graph
        TopologyAgent().execute(state, {
            "topology_preference": profile["topology_preference"],
            "size_topology_override": profile.get("size_topology_override", {}),
            "size": self.request.size,
            "room_count": room_count,
        })

        # StructureAgent: place rooms from graph into terrain
        StructureAgent().execute(state, {
            "type": self.request.map_type,
            "use_room_graph": True,
        })

        # ConnectorAgent: carve corridors, place doors
        ConnectorAgent().execute(state, {
            "corridor_style": profile.get("corridor_style", "carved"),
            "door_frequency": profile.get("door_frequency", 0.5),
        })

        # PathfindingAgent: validate connectivity
        path_result = PathfindingAgent().execute(state, {"mode": "validate"})

        return validate_layout(state, path_result.get("details", {}))

    def run_phase3(self) -> ValidationResult:
        state = self.shared_state
        profile = self.profile

        # RoomPurposeAgent
        RoomPurposeAgent().execute(state, {"profile": profile})

        # EncounterAgent
        EncounterAgent().execute(state, {
            "profile": profile,
            "party_level": self.request.party_level,
            "party_size": self.request.party_size,
        })

        # TrapAgent
        TrapAgent().execute(state, {"profile": profile})

        # LootAgent
        LootAgent().execute(state, {
            "profile": profile,
            "party_level": self.request.party_level,
            "party_size": self.request.party_size,
        })

        # DressingAgent
        DressingAgent().execute(state, {"profile": profile})

        # SpawnAgent (enhanced)
        SpawnAgent().execute(state, {
            "map_type": self.request.map_type,
            "use_encounter_data": True,
        })

        return validate_population(state)

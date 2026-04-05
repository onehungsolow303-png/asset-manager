"""PipelineCoordinator — Orchestrates 3-phase map generation with validation and retry.

Phase 1 (Terrain): TerrainAgent -> WaterAgent -> CaveCarverAgent
Phase 2 (Layout): Stub (implemented in Plan 2)
Phase 3 (Population): Stub (implemented in Plan 3)
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

        # Phase 2: Layout (stub)
        self.run_phase2()

        # Phase 3: Population (stub)
        self.run_phase3()

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
        return validate_layout(self.shared_state)

    def run_phase3(self) -> ValidationResult:
        return validate_population(self.shared_state)

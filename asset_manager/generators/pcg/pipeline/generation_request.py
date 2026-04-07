"""GenerationRequest — input to the PipelineCoordinator."""

from dataclasses import dataclass

VALID_SIZES = [
    "small_encounter", "medium_encounter", "large_encounter",
    "standard", "large", "region", "open_world",
]

VALID_BIOMES = [
    "forest", "mountain", "desert", "swamp", "plains", "tundra",
    "volcanic", "cave", "dungeon", "jungle", "underwater", "sky",
    "flat_floor", "road_ready",
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
        if self.biome not in VALID_BIOMES:
            raise ValueError(f"biome must be one of {VALID_BIOMES}, got '{self.biome}'")

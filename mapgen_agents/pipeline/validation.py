"""Phase validation functions for the generation pipeline."""

from dataclasses import dataclass, field
import numpy as np
from shared_state import SharedState

CAVE_FAMILIES = {"underground", "outdoor", "large_scale"}


@dataclass
class ValidationResult:
    passed: bool
    errors: list[str] = field(default_factory=list)


def validate_terrain(state: SharedState, family: str,
                     min_walkable_pct: float = 0.1) -> ValidationResult:
    """Validate Phase 1 (Terrain) output."""
    errors = []
    h, w = state.config.height, state.config.width
    total_tiles = h * w

    walkable_pct = float(state.walkability.sum()) / total_tiles
    if walkable_pct < min_walkable_pct:
        errors.append(
            f"Insufficient walkable area: {walkable_pct:.1%} < {min_walkable_pct:.1%} required"
        )

    if family in CAVE_FAMILIES:
        if state.cave_mask is None:
            errors.append(f"Cave mask missing for {family} family (expected carving)")
        else:
            cave_open_pct = float(state.cave_mask.sum()) / total_tiles
            if cave_open_pct < 0.05:
                errors.append(
                    f"Cave mask has insufficient open space: {cave_open_pct:.1%} < 5% required"
                )

    return ValidationResult(passed=len(errors) == 0, errors=errors)


def validate_layout(state: SharedState) -> ValidationResult:
    """Validate Phase 2 (Layout) output. Stub for Phase 2 plan."""
    return ValidationResult(passed=True, errors=[])


def validate_population(state: SharedState) -> ValidationResult:
    """Validate Phase 3 (Population) output. Stub for Phase 3 plan."""
    return ValidationResult(passed=True, errors=[])

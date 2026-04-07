"""Phase validation functions for the generation pipeline."""

from dataclasses import dataclass, field
import numpy as np
from asset_manager.shared_state import SharedState

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


def validate_layout(state: SharedState, pathfinding_details: dict = None) -> ValidationResult:
    """Validate Phase 2 (Layout) output."""
    errors = []

    # Check room graph exists
    graph = getattr(state, 'room_graph', None)
    if graph is None or graph.node_count == 0:
        errors.append("No room graph generated")
        return ValidationResult(passed=False, errors=errors)

    # Check all rooms have positions
    unpositioned = [n.node_id for n in graph.nodes if n.position is None]
    if unpositioned:
        errors.append(f"Rooms without positions: {unpositioned}")

    # Check entrance exists
    if graph.entrance_node is None:
        errors.append("No entrance node in room graph")

    # Check connectivity from pathfinding
    if pathfinding_details and not pathfinding_details.get("all_connected", True):
        orphaned = pathfinding_details.get("orphaned_rooms", [])
        errors.append(f"Disconnected rooms: {orphaned}")

    return ValidationResult(passed=len(errors) == 0, errors=errors)


def validate_population(state: SharedState) -> ValidationResult:
    """Validate Phase 3 (Population) output."""
    errors = []
    graph = getattr(state, 'room_graph', None)
    if graph is None:
        return ValidationResult(passed=True, errors=[])  # No graph = skip validation

    # Check all rooms have purposes
    unpurposed = [n.node_id for n in graph.nodes if n.purpose is None]
    if unpurposed:
        errors.append(f"Rooms without purpose: {unpurposed}")

    # Check player spawn exists
    player_spawns = [s for s in state.spawns if s.token_type == "player"]
    if not player_spawns:
        errors.append("No player spawn point")

    return ValidationResult(passed=len(errors) == 0, errors=errors)

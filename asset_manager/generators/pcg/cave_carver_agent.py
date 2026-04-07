"""
CaveCarverAgent — Carves natural cave systems from terrain noise.

Uses dual-threshold carving from raw_elevation + secondary noise, cellular automata
smoothing (B678/S345678 rule), flood fill connectivity enforcement, and natural
opening detection.
"""

import numpy as np
from base_agent import BaseAgent
from shared_state import SharedState
from typing import Any


def _perlin_noise_2d(shape, grid_h, grid_w, seed):
    """
    Generate 2D noise at a coarser grid resolution using bilinear interpolation.
    Mirrors the approach from TerrainAgent's perlin_noise_2d for consistency.
    """
    rng = np.random.default_rng(seed)
    h, w = shape

    gradients = rng.random((grid_h + 1, grid_w + 1)).astype(np.float32)

    y_coords = np.linspace(0, grid_h - 1, h)
    x_coords = np.linspace(0, grid_w - 1, w)
    y_grid, x_grid = np.meshgrid(y_coords, x_coords, indexing='ij')

    y0 = np.floor(y_grid).astype(int)
    x0 = np.floor(x_grid).astype(int)
    y1 = np.minimum(y0 + 1, grid_h)
    x1 = np.minimum(x0 + 1, grid_w)
    fy = y_grid - y0
    fx = x_grid - x0

    # Smoothstep
    fy = fy * fy * (3 - 2 * fy)
    fx = fx * fx * (3 - 2 * fx)

    top = gradients[y0, x0] * (1 - fx) + gradients[y0, x1] * fx
    bot = gradients[y1, x0] * (1 - fx) + gradients[y1, x1] * fx
    noise = top * (1 - fy) + bot * fy

    # Normalize to 0–1
    noise = (noise - noise.min()) / (noise.max() - noise.min() + 1e-8)
    return noise


def _cellular_automata_step(mask: np.ndarray) -> np.ndarray:
    """
    Apply one iteration of B678/S345678 cellular automata.
    True = open (cave space), False = solid wall.
    """
    padded = np.pad(mask.astype(np.int8), 1, mode='constant', constant_values=0)
    neighbor_count = (
        padded[:-2, :-2] + padded[:-2, 1:-1] + padded[:-2, 2:] +
        padded[1:-1, :-2]                     + padded[1:-1, 2:] +
        padded[2:, :-2]  + padded[2:, 1:-1]  + padded[2:, 2:]
    )
    born = (~mask) & (neighbor_count >= 6)
    survive = mask & (neighbor_count >= 3)
    new_mask = born | survive

    # Force edges to solid
    new_mask[0, :] = False
    new_mask[-1, :] = False
    new_mask[:, 0] = False
    new_mask[:, -1] = False

    return new_mask


def _flood_fill(mask: np.ndarray, start_y: int, start_x: int) -> list[tuple[int, int]]:
    """Iterative flood fill returning all connected open tiles as (y, x) tuples."""
    h, w = mask.shape
    visited = np.zeros((h, w), dtype=bool)
    stack = [(start_y, start_x)]
    visited[start_y, start_x] = True
    region = []
    while stack:
        cy, cx = stack.pop()
        region.append((cy, cx))
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                stack.append((ny, nx))
    return region


def _enforce_connectivity(mask: np.ndarray) -> np.ndarray:
    """
    Find all open regions, keep only the largest, fill others back to solid.
    Returns the cleaned mask.
    """
    h, w = mask.shape
    visited = np.zeros((h, w), dtype=bool)
    regions: list[list[tuple[int, int]]] = []

    for y in range(h):
        for x in range(w):
            if mask[y, x] and not visited[y, x]:
                region = _flood_fill(mask, y, x)
                for ry, rx in region:
                    visited[ry, rx] = True
                regions.append(region)

    if not regions:
        return mask

    largest = max(regions, key=len)
    largest_set = set(largest)

    new_mask = np.zeros((h, w), dtype=bool)
    for y in range(h):
        for x in range(w):
            if (y, x) in largest_set:
                new_mask[y, x] = True

    return new_mask


def _detect_openings(
    mask: np.ndarray, min_area: int
) -> list[tuple[int, int, int, int]]:
    """
    Find contiguous sub-areas within the open region using flood fill passes.
    Partitions the open area into chunks separated by thin passages, then returns
    those large enough as (x, y, w, h) bounding boxes.

    Strategy: dilate solid walls slightly to split the cave into sub-rooms, then
    flood fill each sub-region. Any sub-region with area >= min_area is reported.
    """
    h, w = mask.shape

    # Erode open space by 1 pixel to reveal natural room separations
    padded = np.pad(mask.astype(np.int8), 1, mode='constant', constant_values=0)
    neighbor_count = (
        padded[:-2, :-2] + padded[:-2, 1:-1] + padded[:-2, 2:] +
        padded[1:-1, :-2]                     + padded[1:-1, 2:] +
        padded[2:, :-2]  + padded[2:, 1:-1]  + padded[2:, 2:]
    )
    # Only keep tiles that have all 4 cardinal neighbors open (interior tiles)
    eroded = mask & (
        np.roll(mask, -1, axis=0) &
        np.roll(mask, 1, axis=0) &
        np.roll(mask, -1, axis=1) &
        np.roll(mask, 1, axis=1)
    )

    visited = np.zeros((h, w), dtype=bool)
    openings: list[tuple[int, int, int, int]] = []

    for y in range(h):
        for x in range(w):
            if eroded[y, x] and not visited[y, x]:
                region = _flood_fill(eroded, y, x)
                for ry, rx in region:
                    visited[ry, rx] = True
                if len(region) >= min_area:
                    ys = [r[0] for r in region]
                    xs = [r[1] for r in region]
                    min_y, max_y = min(ys), max(ys)
                    min_x, max_x = min(xs), max(xs)
                    bw = max_x - min_x + 1
                    bh = max_y - min_y + 1
                    openings.append((min_x, min_y, bw, bh))

    # Fallback: if no sub-regions found from eroded mask, use the full cave as one opening
    if not openings and mask.any():
        open_tiles = np.argwhere(mask)
        min_y = int(open_tiles[:, 0].min())
        max_y = int(open_tiles[:, 0].max())
        min_x = int(open_tiles[:, 1].min())
        max_x = int(open_tiles[:, 1].max())
        openings.append((min_x, min_y, max_x - min_x + 1, max_y - min_y + 1))

    return openings


class CaveCarverAgent(BaseAgent):
    name = "CaveCarverAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        # Skip mode
        if params.get("skip"):
            return {"skipped": True}

        h, w = shared_state.config.height, shared_state.config.width
        seed = shared_state.config.seed

        carve_threshold = float(params.get("carve_threshold", 0.45))
        passage_threshold = float(params.get("passage_threshold", 0.50))
        smoothing_iterations = int(params.get("smoothing_iterations", 3))

        # --- Step 1: Get raw elevation stored by TerrainAgent ---
        raw_elevation = shared_state.metadata.get("raw_elevation")
        if raw_elevation is None:
            raise ValueError("raw_elevation not found in shared_state.metadata — run TerrainAgent first")

        # --- Step 2: Generate secondary noise at coarser grid for larger features ---
        grid_h = max(2, h // 8)
        grid_w = max(2, w // 8)
        secondary = _perlin_noise_2d((h, w), grid_h, grid_w, seed=seed + 7777)

        # --- Step 3: Dual-threshold carve ---
        mask = (raw_elevation < carve_threshold) & (secondary < passage_threshold)

        # Force edges to solid
        mask[0, :] = False
        mask[-1, :] = False
        mask[:, 0] = False
        mask[:, -1] = False

        # --- Step 4: Cellular automata smoothing (B678/S345678) ---
        for _ in range(smoothing_iterations):
            mask = _cellular_automata_step(mask)

        # --- Step 5: Connectivity — keep only the largest connected region ---
        mask = _enforce_connectivity(mask)

        # --- Step 6: Detect natural openings ---
        min_opening_area = max(20, (h * w) // 200)
        openings = _detect_openings(mask, min_opening_area)

        # --- Step 7: Write results to shared state ---
        shared_state.cave_mask = mask
        shared_state.natural_openings = openings

        open_pct = round(float(mask.mean() * 100), 1)

        return {
            "skipped": False,
            "open_pct": open_pct,
            "openings_found": len(openings),
            "smoothing_iterations": smoothing_iterations,
        }

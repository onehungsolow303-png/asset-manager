"""
WaterAgent — Carves rivers, places lakes, creates water features.
Simulates water flow based on elevation data.
"""

import numpy as np
from .base_agent import BaseAgent
from asset_manager.shared_state import SharedState, PathSegment
from typing import Any
import heapq


class WaterAgent(BaseAgent):
    name = "WaterAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        water_type = params.get("type", "river")
        river_count = params.get("count", 1)
        lake_count = params.get("lake_count", 0)
        stream_count = params.get("stream_count", 0)
        pond_count = params.get("pond_count", 0)
        ocean_edge = params.get("ocean_edge", None)

        rivers_created = 0
        lakes_created = 0
        streams_created = 0
        ponds_created = 0
        has_ocean = False

        # Ocean coastline
        if water_type == "ocean" or ocean_edge:
            self._place_ocean(shared_state, edge=ocean_edge or "south",
                              depth_pct=params.get("ocean_depth_pct", 0.25))
            has_ocean = True

        if water_type in ("river", "both", "ocean_river"):
            for i in range(river_count):
                path = self._carve_river(shared_state, seed_offset=i)
                if path:
                    rivers_created += 1

        if water_type in ("stream",) or stream_count > 0:
            for i in range(max(stream_count, 1) if water_type == "stream" else stream_count):
                path = self._carve_stream(shared_state, seed_offset=i + 50)
                if path:
                    streams_created += 1

        if water_type in ("lake", "both") or lake_count > 0:
            for i in range(max(lake_count, 1)):
                self._place_lake(shared_state, seed_offset=i + 100)
                lakes_created += 1

        if water_type in ("pond",) or pond_count > 0:
            for i in range(max(pond_count, 1) if water_type == "pond" else pond_count):
                self._place_pond(shared_state, seed_offset=i + 150)
                ponds_created += 1

        # Color water areas
        self._color_water(shared_state)

        return {
            "rivers_created": rivers_created,
            "streams_created": streams_created,
            "lakes_created": lakes_created,
            "ponds_created": ponds_created,
            "has_ocean": has_ocean,
            "water_coverage_pct": float(shared_state.water_mask.mean() * 100),
        }

    def _carve_river(self, shared_state: SharedState, seed_offset: int = 0) -> list:
        """
        Simulate river flow: start from a high point, flow downhill to a low point.
        Uses gradient descent with some randomness for natural-looking paths.
        """
        rng = np.random.default_rng(shared_state.config.seed + seed_offset + 200)
        h, w = shared_state.config.height, shared_state.config.width
        elevation = shared_state.elevation

        # Pick start point: high elevation on an edge
        edge = rng.choice(["top", "left", "right"])
        if edge == "top":
            x = rng.integers(w // 4, 3 * w // 4)
            y = 0
        elif edge == "left":
            x = 0
            y = rng.integers(h // 4, 3 * h // 4)
        else:
            x = w - 1
            y = rng.integers(h // 4, 3 * h // 4)

        river_path = [(int(x), int(y))]
        visited = set()
        visited.add((int(x), int(y)))

        max_steps = max(w, h) * 2
        for _ in range(max_steps):
            # Look at 8 neighbors, prefer downhill
            best_next = None
            best_score = float('inf')

            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dy == 0 and dx == 0:
                        continue
                    nx, ny = int(x + dx), int(y + dy)
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                        # Score: prefer lower elevation + slight randomness
                        score = elevation[ny, nx] + rng.random() * 0.05
                        if score < best_score:
                            best_score = score
                            best_next = (nx, ny)

            if best_next is None:
                break

            x, y = best_next
            river_path.append((int(x), int(y)))
            visited.add((int(x), int(y)))

            # Stop if we reach an edge
            if x <= 0 or x >= w - 1 or y <= 0 or y >= h - 1:
                break

        # Apply river to shared state
        river_width = max(2, min(w, h) // 80)
        for px, py in river_path:
            for dy in range(-river_width, river_width + 1):
                for dx in range(-river_width, river_width + 1):
                    nx, ny = px + dx, py + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        if dx*dx + dy*dy <= river_width * river_width:
                            shared_state.water_mask[ny, nx] = True
                            shared_state.walkability[ny, nx] = False

        # Add as path segment
        shared_state.paths.append(PathSegment(
            path_type="river",
            waypoints=river_path,
            width=river_width,
            metadata={"flow_direction": f"{edge}_to_opposite"}
        ))

        return river_path

    def _carve_stream(self, shared_state: SharedState, seed_offset: int = 0) -> list:
        """
        Carve a narrow stream — thinner and shorter than a river, with more
        meandering. Streams are 1-pixel wide and flow over shorter distances.
        """
        rng = np.random.default_rng(shared_state.config.seed + seed_offset + 250)
        h, w = shared_state.config.height, shared_state.config.width
        elevation = shared_state.elevation

        # Start from a random interior point at moderate elevation
        mid_mask = (elevation > np.percentile(elevation, 30)) & \
                   (elevation < np.percentile(elevation, 70))
        mid_points = np.argwhere(mid_mask)
        if len(mid_points) == 0:
            return []

        idx = rng.integers(len(mid_points))
        cy, cx = mid_points[idx]
        x, y = int(cx), int(cy)

        stream_path = [(x, y)]
        visited = {(x, y)}

        # Streams are shorter than rivers
        max_steps = max(w, h)
        for _ in range(max_steps):
            best_next = None
            best_score = float('inf')

            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dy == 0 and dx == 0:
                        continue
                    nx, ny = int(x + dx), int(y + dy)
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                        # More randomness than rivers for meandering
                        score = elevation[ny, nx] + rng.random() * 0.15
                        if score < best_score:
                            best_score = score
                            best_next = (nx, ny)

            if best_next is None:
                break

            x, y = best_next
            stream_path.append((x, y))
            visited.add((x, y))

            # Stop at edge or if we reach very low elevation
            if x <= 0 or x >= w - 1 or y <= 0 or y >= h - 1:
                break
            if elevation[y, x] < np.percentile(elevation, 10):
                break

        # Apply stream — narrower than river (width 1)
        stream_width = max(1, min(w, h) // 160)
        for px, py in stream_path:
            for dy in range(-stream_width, stream_width + 1):
                for dx in range(-stream_width, stream_width + 1):
                    nx, ny = px + dx, py + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        if dx * dx + dy * dy <= stream_width * stream_width:
                            shared_state.water_mask[ny, nx] = True
                            shared_state.walkability[ny, nx] = False

        shared_state.paths.append(PathSegment(
            path_type="stream",
            waypoints=stream_path,
            width=stream_width,
            metadata={"flow_type": "stream"}
        ))

        return stream_path

    def _place_pond(self, shared_state: SharedState, seed_offset: int = 0):
        """Place a small circular pond — much smaller than a lake."""
        rng = np.random.default_rng(shared_state.config.seed + seed_offset + 350)
        h, w = shared_state.config.height, shared_state.config.width

        # Find low-to-mid elevation walkable areas
        walkable = shared_state.walkability & ~shared_state.water_mask
        low_mask = (shared_state.elevation < np.percentile(shared_state.elevation, 50)) & walkable
        low_points = np.argwhere(low_mask)
        if len(low_points) == 0:
            low_points = np.argwhere(walkable)
        if len(low_points) == 0:
            return

        idx = rng.integers(len(low_points))
        cy, cx = low_points[idx]

        # Ponds are small — radius is 1/30 to 1/15 of map dimension
        radius = rng.integers(max(3, min(w, h) // 30), max(5, min(w, h) // 15))

        for y in range(max(0, int(cy) - radius), min(h, int(cy) + radius)):
            for x in range(max(0, int(cx) - radius), min(w, int(cx) + radius)):
                dist = ((x - cx) / max(1, radius)) ** 2 + ((y - cy) / max(1, radius)) ** 2
                noise = rng.random() * 0.25
                if dist + noise < 1.0:
                    shared_state.water_mask[y, x] = True
                    shared_state.walkability[y, x] = False

    def _place_lake(self, shared_state: SharedState, seed_offset: int = 0):
        """Place an elliptical lake in a low-elevation area."""
        rng = np.random.default_rng(shared_state.config.seed + seed_offset + 300)
        h, w = shared_state.config.height, shared_state.config.width

        # Find low-elevation areas
        low_mask = shared_state.elevation < np.percentile(shared_state.elevation, 30)
        low_points = np.argwhere(low_mask)
        if len(low_points) == 0:
            return

        # Pick a random low point as center
        idx = rng.integers(len(low_points))
        cy, cx = low_points[idx]

        # Random ellipse size
        radius_x = rng.integers(w // 20, w // 8)
        radius_y = rng.integers(h // 20, h // 8)

        for y in range(max(0, cy - radius_y), min(h, cy + radius_y)):
            for x in range(max(0, cx - radius_x), min(w, cx + radius_x)):
                # Ellipse equation + noise for organic shape
                dist = ((x - cx) / radius_x) ** 2 + ((y - cy) / radius_y) ** 2
                noise = rng.random() * 0.3
                if dist + noise < 1.0:
                    shared_state.water_mask[y, x] = True
                    shared_state.walkability[y, x] = False

    def _place_ocean(self, shared_state: SharedState, edge: str = "south",
                      depth_pct: float = 0.25):
        """Place an ocean along one edge with organic coastline using noise."""
        rng = np.random.default_rng(shared_state.config.seed + 900)
        h, w = shared_state.config.height, shared_state.config.width

        # Base depth in pixels from the edge
        base_depth = int(max(h, w) * depth_pct)

        # Generate coastline noise
        coast_len = w if edge in ("south", "north") else h
        coast_noise = np.zeros(coast_len)
        for i in range(coast_len):
            # Multi-frequency noise for organic coastline
            coast_noise[i] = (
                np.sin(i * 0.02) * base_depth * 0.3 +
                np.sin(i * 0.07 + 1.5) * base_depth * 0.15 +
                rng.random() * base_depth * 0.1
            )

        for i in range(coast_len):
            line_depth = int(base_depth + coast_noise[i])
            for d in range(line_depth):
                if edge == "south":
                    x, y = i, h - 1 - d
                elif edge == "north":
                    x, y = i, d
                elif edge == "west":
                    x, y = d, i
                else:  # east
                    x, y = w - 1 - d, i

                if 0 <= x < w and 0 <= y < h:
                    shared_state.water_mask[y, x] = True
                    shared_state.walkability[y, x] = False
                    # Deeper blue further from shore
                    depth_ratio = d / max(1, line_depth)
                    shared_state.elevation[y, x] = 0.1 * (1 - depth_ratio)

        # Add beach/sand strip along coastline
        beach_width = max(2, base_depth // 8)
        sand_color = (194, 178, 128)
        for i in range(coast_len):
            line_depth = int(base_depth + coast_noise[i])
            for d in range(beach_width):
                bd = line_depth + d
                if edge == "south":
                    x, y = i, h - 1 - bd
                elif edge == "north":
                    x, y = i, bd
                elif edge == "west":
                    x, y = bd, i
                else:
                    x, y = w - 1 - bd, i
                if 0 <= x < w and 0 <= y < h and not shared_state.water_mask[y, x]:
                    shared_state.terrain_color[y, x] = sand_color

    def _color_water(self, shared_state: SharedState):
        """Apply water colors to the terrain color layer."""
        water_color_deep = np.array([30, 80, 140], dtype=np.uint8)
        water_color_shallow = np.array([60, 130, 180], dtype=np.uint8)

        h, w = shared_state.config.height, shared_state.config.width
        for y in range(h):
            for x in range(w):
                if shared_state.water_mask[y, x]:
                    # Deeper water in center of water bodies
                    depth = min(1.0, shared_state.elevation[y, x])
                    color = (water_color_deep * (1 - depth) +
                             water_color_shallow * depth).astype(np.uint8)
                    shared_state.terrain_color[y, x] = color

"""
PathfindingAgent — Establishes road/trail networks using A* and MST algorithms.
Creates natural-looking paths that avoid water and steep terrain.
"""

import numpy as np
from base_agent import BaseAgent
from shared_state import SharedState, PathSegment
from typing import Any
import heapq


def astar(grid: np.ndarray, start: tuple, end: tuple,
          elevation: np.ndarray = None) -> list[tuple[int, int]]:
    """
    A* pathfinding on a 2D grid.
    grid: boolean walkability mask (True = walkable)
    Returns list of (x, y) waypoints or empty list if no path found.
    """
    h, w = grid.shape

    def heuristic(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == end:
            # Reconstruct path
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            return path[::-1]

        cx, cy = current
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1),
                        (-1, -1), (-1, 1), (1, -1), (1, 1)]:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < w and 0 <= ny < h and grid[ny, nx]:
                move_cost = 1.414 if (dx != 0 and dy != 0) else 1.0
                # Add elevation cost if available
                if elevation is not None:
                    elev_diff = abs(float(elevation[ny, nx]) - float(elevation[cy, cx]))
                    move_cost += elev_diff * 5.0
                tentative_g = g_score[current] + move_cost
                neighbor = (nx, ny)
                if tentative_g < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + heuristic(neighbor, end)
                    heapq.heappush(open_set, (f_score, neighbor))

    return []  # No path found


class PathfindingAgent(BaseAgent):
    name = "PathfindingAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        algorithm = params.get("algorithm", "a_star")
        road_density = params.get("road_density", "medium")
        road_type = params.get("road_type", "road")

        density_map = {"low": 2, "medium": 4, "high": 7}
        num_roads = density_map.get(road_density, 4)

        h, w = shared_state.config.height, shared_state.config.width
        rng = np.random.default_rng(shared_state.config.seed + 400)

        walkable = shared_state.get_walkable_positions()
        walkable_points = np.argwhere(walkable)
        if len(walkable_points) < 2:
            return {"roads_created": 0, "error": "Not enough walkable space"}

        roads_created = 0
        road_width = max(1, min(w, h) // 150)

        # Generate POI candidates spread across the map
        poi_count = num_roads + 2
        pois = self._generate_spread_points(walkable_points, poi_count, rng)

        # Connect POIs using MST-like approach (nearest neighbor chain)
        connected = {0}
        edges = []

        while len(connected) < len(pois):
            best_dist = float('inf')
            best_edge = None
            for i in connected:
                for j in range(len(pois)):
                    if j not in connected:
                        dist = np.sqrt((pois[i][0] - pois[j][0])**2 +
                                       (pois[i][1] - pois[j][1])**2)
                        if dist < best_dist:
                            best_dist = dist
                            best_edge = (i, j)
            if best_edge:
                edges.append(best_edge)
                connected.add(best_edge[1])
            else:
                break

        # Pathfind between connected POIs
        for i, j in edges:
            start = (int(pois[i][1]), int(pois[i][0]))  # (x, y)
            end = (int(pois[j][1]), int(pois[j][0]))

            path = astar(walkable, start, end, shared_state.elevation)
            if path:
                # Apply road to map
                for px, py in path:
                    for dy in range(-road_width, road_width + 1):
                        for dx in range(-road_width, road_width + 1):
                            nx, ny = px + dx, py + dy
                            if 0 <= nx < w and 0 <= ny < h:
                                shared_state.walkability[ny, nx] = True
                                # Road color
                                shared_state.terrain_color[ny, nx] = self._road_color(
                                    shared_state.config.biome)

                shared_state.paths.append(PathSegment(
                    path_type=road_type,
                    waypoints=path,
                    width=road_width,
                ))
                roads_created += 1

        return {
            "roads_created": roads_created,
            "poi_count": len(pois),
            "algorithm": algorithm,
        }

    def _generate_spread_points(self, walkable: np.ndarray, count: int,
                                 rng: np.random.Generator) -> list:
        """Pick well-spread points from walkable areas using farthest-point sampling."""
        indices = rng.choice(len(walkable), size=min(count * 20, len(walkable)), replace=False)
        candidates = walkable[indices]

        if len(candidates) <= count:
            return candidates.tolist()

        # Farthest-point sampling
        selected = [candidates[0].tolist()]
        for _ in range(count - 1):
            max_dist = -1
            best_point = None
            for c in candidates:
                min_d = min(np.sqrt((c[0]-s[0])**2 + (c[1]-s[1])**2) for s in selected)
                if min_d > max_dist:
                    max_dist = min_d
                    best_point = c.tolist()
            if best_point:
                selected.append(best_point)

        return selected

    def _road_color(self, biome: str) -> tuple:
        road_colors = {
            "forest": (140, 115, 80),
            "mountain": (150, 140, 125),
            "desert": (170, 150, 110),
            "swamp": (100, 90, 65),
            "plains": (160, 140, 100),
            "tundra": (170, 175, 180),
            "volcanic": (80, 65, 55),
            "cave": (90, 85, 75),
            "dungeon": (90, 85, 75),
        }
        return road_colors.get(biome, (140, 115, 80))

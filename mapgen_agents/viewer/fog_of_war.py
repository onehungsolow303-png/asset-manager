"""Three-state fog of war with LOS raycasting."""

import math
import numpy as np
from config import FOW_SIGHT_RADIUS

# Fog states
UNEXPLORED = 0
EXPLORED = 1
VISIBLE = 2


class FogOfWar:
    """Per-z-level fog of war with three visibility states."""

    def __init__(self):
        self._fog: dict[int, np.ndarray] = {}
        self.enabled = True

    def get_or_create(self, z: int, width: int = 0, height: int = 0) -> np.ndarray:
        """Lazy-init fog state for a z-level."""
        if z not in self._fog:
            self._fog[z] = np.full((height, width), UNEXPLORED, dtype=np.uint8)
        return self._fog[z]

    def update(self, player_x: int, player_y: int, player_z: int,
               walkability: dict):
        """Update fog: dim previous VISIBLE to EXPLORED, then raycast LOS."""
        if not self.enabled:
            return

        walk = walkability.get(player_z)
        if walk is None:
            return

        h, w = walk.shape
        fog = self.get_or_create(player_z, w, h)

        # Dim all currently visible tiles to explored
        fog[fog == VISIBLE] = EXPLORED

        # Raycast 360 rays from player position
        num_rays = 360
        radius = FOW_SIGHT_RADIUS

        for i in range(num_rays):
            angle = 2.0 * math.pi * i / num_rays
            dx = math.cos(angle)
            dy = math.sin(angle)

            rx = player_x + 0.5
            ry = player_y + 0.5

            for step in range(radius):
                tx = int(rx)
                ty = int(ry)

                if tx < 0 or tx >= w or ty < 0 or ty >= h:
                    break

                fog[ty, tx] = VISIBLE

                # Stop if we hit a wall (but mark the wall tile itself visible)
                if not walk[ty, tx]:
                    break

                rx += dx
                ry += dy

    def toggle(self):
        """Enable / disable fog of war."""
        self.enabled = not self.enabled

    def is_visible(self, x: int, y: int, z: int) -> bool:
        """Check if a tile is currently visible."""
        if not self.enabled:
            return True
        fog = self._fog.get(z)
        if fog is None:
            return False
        h, w = fog.shape
        if 0 <= x < w and 0 <= y < h:
            return fog[y, x] == VISIBLE
        return False

    def get_state(self, x: int, y: int, z: int) -> int:
        """Return fog state for a tile."""
        if not self.enabled:
            return VISIBLE
        fog = self._fog.get(z)
        if fog is None:
            return UNEXPLORED
        h, w = fog.shape
        if 0 <= x < w and 0 <= y < h:
            return fog[y, x]
        return UNEXPLORED

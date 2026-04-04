"""Camera with smooth follow, zoom, pan, and parallax offset."""

import math
from config import (
    TILE_SIZE, PARALLAX_STRENGTH, WINDOW_WIDTH, WINDOW_HEIGHT,
)


class Camera:
    """Viewport camera with smooth follow, zoom, pan, and parallax."""

    def __init__(self, screen_w: int = WINDOW_WIDTH, screen_h: int = WINDOW_HEIGHT):
        self.screen_w = screen_w
        self.screen_h = screen_h

        # World position the camera is centred on (pixels)
        self.x = 0.0
        self.y = 0.0

        # Smooth-follow target
        self._target_x = 0.0
        self._target_y = 0.0
        self._follow_speed = 0.12  # interpolation factor per frame

        # Zoom
        self.zoom = 2.0
        self._zoom_min = 0.25
        self._zoom_max = 4.0

        # Pan offset (added on top of follow target)
        self._pan_x = 0.0
        self._pan_y = 0.0

        # Parallax
        self.perspective_mode = False
        self._mouse_x = screen_w // 2
        self._mouse_y = screen_h // 2

        # Track the player z-level for renderer z-offset calcs
        self._player_z = 0

    # ------------------------------------------------------------------
    # Follow
    # ------------------------------------------------------------------
    def follow(self, world_x: float, world_y: float):
        """Set the follow target (world pixel coords)."""
        self._target_x = world_x
        self._target_y = world_y

    def update(self):
        """Smooth interpolation toward the follow target."""
        target_x = self._target_x + self._pan_x
        target_y = self._target_y + self._pan_y
        self.x += (target_x - self.x) * self._follow_speed
        self.y += (target_y - self.y) * self._follow_speed

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------
    def zoom_in(self):
        self.zoom = min(self._zoom_max, self.zoom * 1.15)

    def zoom_out(self):
        self.zoom = max(self._zoom_min, self.zoom / 1.15)

    # ------------------------------------------------------------------
    # Pan
    # ------------------------------------------------------------------
    def pan(self, dx: float, dy: float):
        """Offset by screen-space delta (converted to world coords)."""
        self._pan_x -= dx / self.zoom
        self._pan_y -= dy / self.zoom

    # ------------------------------------------------------------------
    # Coordinate transforms
    # ------------------------------------------------------------------
    def world_to_screen(self, wx: float, wy: float, z_offset: float = 0.0):
        """Convert world coords to screen coords, with optional parallax."""
        sx = (wx - self.x) * self.zoom + self.screen_w / 2
        sy = (wy - self.y) * self.zoom + self.screen_h / 2

        if self.perspective_mode and z_offset != 0:
            # Parallax: shift based on mouse position relative to screen centre
            cx = self._mouse_x - self.screen_w / 2
            cy = self._mouse_y - self.screen_h / 2
            strength = PARALLAX_STRENGTH * z_offset
            sx += cx * strength
            sy += cy * strength

        return sx, sy

    def screen_to_world(self, sx: float, sy: float):
        """Convert screen coords to world coords."""
        wx = (sx - self.screen_w / 2) / self.zoom + self.x
        wy = (sy - self.screen_h / 2) / self.zoom + self.y
        return wx, wy

    def visible_tile_range(self):
        """Return (x1, y1, x2, y2) of visible tiles in tile coords."""
        # Top-left and bottom-right world coords
        w_tl_x, w_tl_y = self.screen_to_world(0, 0)
        w_br_x, w_br_y = self.screen_to_world(self.screen_w, self.screen_h)

        # Convert to tile coords with padding
        pad = 2
        x1 = int(w_tl_x / TILE_SIZE) - pad
        y1 = int(w_tl_y / TILE_SIZE) - pad
        x2 = int(math.ceil(w_br_x / TILE_SIZE)) + pad
        y2 = int(math.ceil(w_br_y / TILE_SIZE)) + pad
        return x1, y1, x2, y2

    # ------------------------------------------------------------------
    # Perspective / resize
    # ------------------------------------------------------------------
    def toggle_perspective(self):
        """Flip perspective (parallax) mode."""
        self.perspective_mode = not self.perspective_mode

    def set_mouse(self, mx: int, my: int):
        """Update mouse position for parallax calculation."""
        self._mouse_x = mx
        self._mouse_y = my

    def resize(self, w: int, h: int):
        """Handle window resize."""
        self.screen_w = w
        self.screen_h = h

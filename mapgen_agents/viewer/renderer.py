"""Tile-based renderer: terrain, tokens, fog overlay, grid."""

import pygame
import numpy as np
from config import (
    TILE_SIZE, TOKEN_RADIUS, TOKEN_BORDER,
    COLOR_BLACK, COLOR_WHITE, COLOR_PLAYER, COLOR_PLAYER_BORDER,
    COLOR_ENEMY, COLOR_ENEMY_BORDER, COLOR_NPC, COLOR_NPC_BORDER,
    COLOR_FOG_UNEXPLORED, COLOR_HP_GREEN, COLOR_HP_RED, COLOR_HP_BG,
    COLOR_GRID, COLOR_TRANSITION,
)
from fog_of_war import UNEXPLORED, EXPLORED, VISIBLE


def pil_to_surface(pil_image) -> pygame.Surface:
    """Convert a PIL RGB image to a pygame Surface."""
    mode = pil_image.mode
    size = pil_image.size
    data = pil_image.tobytes()
    return pygame.image.fromstring(data, size, mode)


class Renderer:
    """Draws terrain, creatures, fog, and grid to the pygame screen."""

    def __init__(self, screen: pygame.Surface, game_map):
        self.screen = screen
        self.game_map = game_map
        self.show_grid = False

        # Convert PIL terrain images to pygame Surfaces
        for z, pil_img in game_map.terrain_images.items():
            game_map.terrain_surfaces[z] = pil_to_surface(pil_img)

    def render(self, camera, creatures, fog, player_z: int, engine):
        """Main render call."""
        self.screen.fill(COLOR_BLACK)

        z_levels = self.game_map.z_levels

        # 1. Draw z-level below current (dimmed)
        if player_z - 1 in z_levels:
            self._draw_terrain(camera, player_z - 1, dimmed=True,
                               z_offset=-1)

        # 2. Draw current z-level terrain
        self._draw_terrain(camera, player_z, dimmed=False, z_offset=0)

        # 3. Draw transition markers
        self._draw_transitions(camera, player_z)

        # 4. Draw creature tokens
        self._draw_creatures(camera, creatures, fog, player_z)

        # 5. Draw fog of war overlay
        self._draw_fog(camera, fog, player_z)

        # 6. Draw grid if enabled
        if self.show_grid:
            self._draw_grid(camera, player_z)

    def _draw_terrain(self, camera, z: int, dimmed: bool, z_offset: float):
        """Draw a z-level's terrain image."""
        surface = self.game_map.terrain_surfaces.get(z)
        if surface is None:
            return

        img_w, img_h = surface.get_size()

        # World-space top-left of this z-level's image
        sx, sy = camera.world_to_screen(0, 0, z_offset)

        # Scale the surface
        scaled_w = int(img_w * camera.zoom)
        scaled_h = int(img_h * camera.zoom)

        if scaled_w <= 0 or scaled_h <= 0:
            return

        scaled = pygame.transform.scale(surface, (scaled_w, scaled_h))

        if dimmed:
            scaled.set_alpha(128)

        self.screen.blit(scaled, (int(sx), int(sy)))

    def _draw_transitions(self, camera, player_z: int):
        """Draw purple rectangles at transition points."""
        for t in self.game_map.transitions:
            if t["from_z"] != player_z:
                continue

            tx, ty = t["x"], t["y"]
            sx, sy = camera.world_to_screen(tx * TILE_SIZE, ty * TILE_SIZE)
            size = max(2, int(TILE_SIZE * camera.zoom))

            rect = pygame.Rect(int(sx), int(sy), size, size)
            # Semi-transparent purple
            trans_surf = pygame.Surface((size, size), pygame.SRCALPHA)
            trans_surf.fill((*COLOR_TRANSITION, 160))
            self.screen.blit(trans_surf, rect.topleft)

            # Border
            pygame.draw.rect(self.screen, COLOR_TRANSITION, rect, 1)

    def _draw_creatures(self, camera, creatures, fog, player_z: int):
        """Draw creature tokens (colored circles with letter + HP bars)."""
        for c in creatures:
            if not c.alive or c.z != player_z:
                continue

            # Skip creatures in unexplored fog (but show in explored/visible)
            if fog.enabled:
                state = fog.get_state(c.x, c.y, c.z)
                if state == UNEXPLORED:
                    continue
                # In explored but not visible, don't show enemies
                if state == EXPLORED and c.token_type == "enemy":
                    continue

            # Update creature visibility flag
            c.visible = fog.is_visible(c.x, c.y, c.z)

            # World centre of the creature's tile
            wx = c.x * TILE_SIZE + TILE_SIZE / 2
            wy = c.y * TILE_SIZE + TILE_SIZE / 2
            sx, sy = camera.world_to_screen(wx, wy)
            sx, sy = int(sx), int(sy)

            radius = max(3, int(TOKEN_RADIUS * camera.zoom))
            border = max(1, int(TOKEN_BORDER * camera.zoom))

            # Colour by type
            if c.token_type == "player":
                fill, outline = COLOR_PLAYER, COLOR_PLAYER_BORDER
            elif c.token_type == "enemy":
                fill, outline = COLOR_ENEMY, COLOR_ENEMY_BORDER
            else:
                fill, outline = COLOR_NPC, COLOR_NPC_BORDER

            # Circle
            pygame.draw.circle(self.screen, fill, (sx, sy), radius)
            pygame.draw.circle(self.screen, outline, (sx, sy), radius, border)

            # Letter
            font_size = max(10, int(12 * camera.zoom))
            try:
                font = pygame.font.SysFont("consolas", font_size)
            except Exception:
                font = pygame.font.Font(None, font_size)
            letter = c.name[0].upper() if c.name else "?"
            text = font.render(letter, True, COLOR_WHITE)
            tr = text.get_rect(center=(sx, sy))
            self.screen.blit(text, tr)

            # HP bar (only if damaged)
            if c.hp < c.max_hp:
                bar_w = int(TILE_SIZE * camera.zoom * 0.9)
                bar_h = max(2, int(3 * camera.zoom))
                bar_x = sx - bar_w // 2
                bar_y = sy + radius + 2

                # Background
                pygame.draw.rect(self.screen, COLOR_HP_BG,
                                 (bar_x, bar_y, bar_w, bar_h))
                # Fill
                fill_w = int(bar_w * c.hp_pct)
                color = COLOR_HP_GREEN if c.hp_pct > 0.5 else COLOR_HP_RED
                pygame.draw.rect(self.screen, color,
                                 (bar_x, bar_y, fill_w, bar_h))

    def _draw_fog(self, camera, fog, player_z: int):
        """Draw fog overlay: UNEXPLORED=black, EXPLORED=semi-transparent."""
        if not fog.enabled:
            return

        fog_arr = fog._fog.get(player_z)
        if fog_arr is None:
            return

        h, w = fog_arr.shape
        x1, y1, x2, y2 = camera.visible_tile_range()
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)

        tile_px = max(1, int(TILE_SIZE * camera.zoom))

        # Create fog tile surfaces (cached size)
        fog_black = pygame.Surface((tile_px, tile_px), pygame.SRCALPHA)
        fog_black.fill((0, 0, 0, 255))
        fog_dim = pygame.Surface((tile_px, tile_px), pygame.SRCALPHA)
        fog_dim.fill((0, 0, 0, 128))

        for ty in range(y1, y2):
            for tx in range(x1, x2):
                state = fog_arr[ty, tx]
                if state == VISIBLE:
                    continue

                sx, sy = camera.world_to_screen(tx * TILE_SIZE, ty * TILE_SIZE)
                pos = (int(sx), int(sy))

                if state == UNEXPLORED:
                    self.screen.blit(fog_black, pos)
                elif state == EXPLORED:
                    self.screen.blit(fog_dim, pos)

    def _draw_grid(self, camera, player_z: int):
        """Draw a subtle tile grid overlay."""
        x1, y1, x2, y2 = camera.visible_tile_range()
        map_w = self.game_map.width
        map_h = self.game_map.height
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(map_w, x2)
        y2 = min(map_h, y2)

        grid_surf = pygame.Surface(
            (self.screen.get_width(), self.screen.get_height()),
            pygame.SRCALPHA
        )
        color = COLOR_GRID

        for tx in range(x1, x2 + 1):
            sx, sy_top = camera.world_to_screen(tx * TILE_SIZE, y1 * TILE_SIZE)
            _, sy_bot = camera.world_to_screen(tx * TILE_SIZE, y2 * TILE_SIZE)
            pygame.draw.line(grid_surf, color,
                             (int(sx), int(sy_top)), (int(sx), int(sy_bot)), 1)

        for ty in range(y1, y2 + 1):
            sx_left, sy = camera.world_to_screen(x1 * TILE_SIZE, ty * TILE_SIZE)
            sx_right, _ = camera.world_to_screen(x2 * TILE_SIZE, ty * TILE_SIZE)
            pygame.draw.line(grid_surf, color,
                             (int(sx_left), int(sy)), (int(sx_right), int(sy)), 1)

        self.screen.blit(grid_surf, (0, 0))

    def toggle_grid(self):
        """Toggle grid overlay."""
        self.show_grid = not self.show_grid

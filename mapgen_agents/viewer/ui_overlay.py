"""HUD overlay: stats panel, combat log, turn order, mode indicator, minimap."""

import pygame
import numpy as np
from config import (
    TILE_SIZE,
    COLOR_BLACK, COLOR_WHITE, COLOR_UI_BG, COLOR_UI_TEXT,
    COLOR_UI_GOLD, COLOR_HP_GREEN, COLOR_HP_RED, COLOR_HP_BG,
    COLOR_PLAYER, COLOR_ENEMY, COLOR_NPC,
)
from fog_of_war import UNEXPLORED, EXPLORED, VISIBLE
from game_engine import GameState


class UIOverlay:
    """Draws all HUD elements on top of the game view."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self._font = None
        self._font_small = None
        self._font_large = None
        self._minimap_cache = {}  # z -> pygame.Surface
        self._init_fonts()

    def _init_fonts(self):
        """Initialize fonts (call after pygame.init)."""
        try:
            self._font = pygame.font.SysFont("consolas", 14)
            self._font_small = pygame.font.SysFont("consolas", 12)
            self._font_large = pygame.font.SysFont("consolas", 18)
        except Exception:
            self._font = pygame.font.Font(None, 16)
            self._font_small = pygame.font.Font(None, 14)
            self._font_large = pygame.font.Font(None, 20)

    def render(self, engine, player, creatures, camera, fog=None, game_map=None):
        """Draw all HUD elements."""
        self._draw_mode_indicator(engine, camera)
        self._draw_player_stats(player)
        self._draw_combat_log(engine)

        if engine.state == GameState.COMBAT:
            self._draw_turn_order(engine)

        if game_map is not None:
            self._draw_minimap(player, creatures, fog, game_map, camera)

    def _draw_mode_indicator(self, engine, camera):
        """Draw mode indicator top-left: state, z-level, perspective."""
        x, y = 10, 10

        # Game state
        if engine.state == GameState.EXPLORATION:
            text = "EXPLORATION"
            color = (34, 197, 94)  # green
        elif engine.state == GameState.COMBAT:
            text = "COMBAT"
            color = COLOR_UI_GOLD
        else:
            text = "GAME OVER"
            color = (239, 68, 68)  # red

        surf = self._font_large.render(text, True, color)
        # Background
        bg = pygame.Surface((surf.get_width() + 16, surf.get_height() + 8),
                            pygame.SRCALPHA)
        bg.fill((*COLOR_UI_BG[:3], COLOR_UI_BG[3] if len(COLOR_UI_BG) > 3 else 220))
        self.screen.blit(bg, (x - 4, y - 4))
        self.screen.blit(surf, (x + 4, y))
        y += surf.get_height() + 8

        # Z-level
        z_text = f"Z-Level: {camera._player_z}"
        z_surf = self._font.render(z_text, True, COLOR_UI_TEXT)
        self.screen.blit(z_surf, (x + 4, y))
        y += z_surf.get_height() + 4

        # Perspective mode
        if camera.perspective_mode:
            p_surf = self._font_small.render("Perspective ON", True, COLOR_UI_GOLD)
            self.screen.blit(p_surf, (x + 4, y))

    def _draw_player_stats(self, player):
        """Draw player stats panel (top-right)."""
        panel_w = 180
        panel_h = 160
        sw = self.screen.get_width()
        x = sw - panel_w - 10
        y = 10

        # Background
        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((*COLOR_UI_BG[:3], COLOR_UI_BG[3] if len(COLOR_UI_BG) > 3 else 220))
        self.screen.blit(bg, (x, y))

        pad = 8
        cx = x + pad
        cy = y + pad

        # Name
        name_surf = self._font.render(player.name, True, COLOR_PLAYER)
        self.screen.blit(name_surf, (cx, cy))
        cy += name_surf.get_height() + 6

        # HP bar
        hp_text = f"HP: {player.hp}/{player.max_hp}"
        hp_surf = self._font_small.render(hp_text, True, COLOR_UI_TEXT)
        self.screen.blit(hp_surf, (cx, cy))
        cy += hp_surf.get_height() + 2

        bar_w = panel_w - pad * 2
        bar_h = 8
        pygame.draw.rect(self.screen, COLOR_HP_BG, (cx, cy, bar_w, bar_h))
        fill_w = int(bar_w * player.hp_pct)
        bar_color = COLOR_HP_GREEN if player.hp_pct > 0.5 else COLOR_HP_RED
        pygame.draw.rect(self.screen, bar_color, (cx, cy, fill_w, bar_h))
        cy += bar_h + 8

        # Stats
        stats = [
            f"AC: {player.ac}",
            f"STR: {player.strength}  DEX: {player.dexterity}",
            f"SPD: {player.speed}  ATK: {player.atk_dice}",
        ]
        for s in stats:
            s_surf = self._font_small.render(s, True, COLOR_UI_TEXT)
            self.screen.blit(s_surf, (cx, cy))
            cy += s_surf.get_height() + 3

    def _draw_combat_log(self, engine):
        """Draw combat log at the bottom of the screen."""
        max_lines = 8
        log_lines = engine.log[-max_lines:]

        if not log_lines:
            return

        sh = self.screen.get_height()
        sw = self.screen.get_width()

        line_h = 16
        panel_h = len(log_lines) * line_h + 12
        panel_w = sw - 20
        x = 10
        y = sh - panel_h - 10

        # Background
        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((*COLOR_UI_BG[:3], COLOR_UI_BG[3] if len(COLOR_UI_BG) > 3 else 220))
        self.screen.blit(bg, (x, y))

        cy = y + 6
        for line in log_lines:
            color = self._log_color(line)
            text = self._font_small.render(line, True, color)
            self.screen.blit(text, (x + 8, cy))
            cy += line_h

    def _log_color(self, line: str) -> tuple:
        """Color-code a log line."""
        lower = line.lower()
        if "hits" in lower or "damage" in lower:
            return (239, 68, 68)  # red
        if "misses" in lower:
            return (156, 163, 175)  # gray
        if "defeated" in lower or "victory" in lower:
            return COLOR_UI_GOLD
        if "round" in lower:
            return (147, 197, 253)  # light blue
        if "game over" in lower:
            return (239, 68, 68)
        return COLOR_UI_TEXT

    def _draw_turn_order(self, engine):
        """Draw turn order panel (right side, combat only)."""
        if not engine.combat.active:
            return

        panel_w = 160
        line_h = 22
        combatants = [c for c in engine.combat.turn_order if c.alive]
        panel_h = len(combatants) * line_h + 30

        sw = self.screen.get_width()
        x = sw - panel_w - 10
        y = 180  # below stats panel

        # Background
        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((*COLOR_UI_BG[:3], COLOR_UI_BG[3] if len(COLOR_UI_BG) > 3 else 220))
        self.screen.blit(bg, (x, y))

        # Title
        title = self._font.render("Turn Order", True, COLOR_UI_GOLD)
        self.screen.blit(title, (x + 8, y + 6))

        cy = y + 26
        current = engine.combat.current_creature

        for c in combatants:
            # Highlight current
            if c is current:
                hi = pygame.Surface((panel_w - 4, line_h), pygame.SRCALPHA)
                hi.fill((255, 255, 255, 30))
                self.screen.blit(hi, (x + 2, cy))

            # Color by type
            if c.token_type == "player":
                color = COLOR_PLAYER
            elif c.token_type == "enemy":
                color = COLOR_ENEMY
            else:
                color = COLOR_NPC

            text = f"{c.name} ({c.hp}/{c.max_hp})"
            surf = self._font_small.render(text, True, color)
            self.screen.blit(surf, (x + 8, cy + 3))

            # Arrow for current
            if c is current:
                arrow = self._font_small.render(">", True, COLOR_UI_GOLD)
                self.screen.blit(arrow, (x + panel_w - 18, cy + 3))

            cy += line_h

    def _draw_minimap(self, player, creatures, fog, game_map, camera):
        """Draw a minimap in the bottom-right corner."""
        sw = self.screen.get_width()
        sh = self.screen.get_height()

        # Minimap size: scale to fit 160px max dimension
        map_w = game_map.width
        map_h = game_map.height
        max_dim = 160
        scale = min(max_dim / map_w, max_dim / map_h)
        mm_w = int(map_w * scale)
        mm_h = int(map_h * scale)

        margin = 10
        mm_x = sw - mm_w - margin
        mm_y = sh - mm_h - margin - 10

        # Background
        bg = pygame.Surface((mm_w + 4, mm_h + 4), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 200))
        self.screen.blit(bg, (mm_x - 2, mm_y - 2))

        # Draw terrain from cached minimap surface
        pz = player.z if player else 0
        if pz not in self._minimap_cache:
            terrain_img = game_map.terrain_images.get(pz)
            if terrain_img is not None:
                import PIL.Image
                mini_pil = terrain_img.resize((mm_w, mm_h), PIL.Image.Resampling.NEAREST)
                mini_data = mini_pil.tobytes()
                self._minimap_cache[pz] = pygame.image.fromstring(
                    mini_data, (mm_w, mm_h), "RGB")
            else:
                s = pygame.Surface((mm_w, mm_h))
                s.fill((40, 40, 40))
                self._minimap_cache[pz] = s

        mini_surf = self._minimap_cache[pz].copy()

        # Apply fog to minimap (numpy-accelerated)
        if fog is not None and fog.enabled:
            fog_arr = fog._fog.get(pz)
            if fog_arr is not None:
                # Resample fog to minimap size using nearest-neighbor
                fh, fw = fog_arr.shape
                ys = np.clip((np.arange(mm_h) / scale).astype(int), 0, fh - 1)
                xs = np.clip((np.arange(mm_w) / scale).astype(int), 0, fw - 1)
                fog_mini = fog_arr[np.ix_(ys, xs)]

                # Build RGBA overlay: unexplored=black opaque, explored=black semi
                alpha = np.zeros((mm_h, mm_w), dtype=np.uint8)
                alpha[fog_mini == UNEXPLORED] = 255
                alpha[fog_mini == EXPLORED] = 140
                # VISIBLE tiles get alpha=0 (transparent)

                fog_rgba = np.zeros((mm_h, mm_w, 4), dtype=np.uint8)
                fog_rgba[:, :, 3] = alpha

                fog_overlay = pygame.image.frombuffer(
                    fog_rgba.tobytes(), (mm_w, mm_h), "RGBA")
                mini_surf.blit(fog_overlay, (0, 0))

        self.screen.blit(mini_surf, (mm_x, mm_y))

        # Draw creature dots
        for c in creatures:
            if not c.alive or c.z != pz:
                continue
            cx = int(c.x * scale)
            cy_pos = int(c.y * scale)
            if c.token_type == "player":
                color = COLOR_PLAYER
                r = 3
            elif c.token_type == "enemy":
                if fog is not None and fog.enabled and not fog.is_visible(c.x, c.y, c.z):
                    continue
                color = COLOR_ENEMY
                r = 2
            else:
                color = COLOR_NPC
                r = 2
            pygame.draw.circle(self.screen, color, (mm_x + cx, mm_y + cy_pos), r)

        # Draw viewport rectangle
        w_tl_x, w_tl_y = camera.screen_to_world(0, 0)
        w_br_x, w_br_y = camera.screen_to_world(camera.screen_w, camera.screen_h)
        vx1 = int(w_tl_x / TILE_SIZE * scale)
        vy1 = int(w_tl_y / TILE_SIZE * scale)
        vx2 = int(w_br_x / TILE_SIZE * scale)
        vy2 = int(w_br_y / TILE_SIZE * scale)
        vx1 = max(0, min(mm_w, vx1))
        vy1 = max(0, min(mm_h, vy1))
        vx2 = max(0, min(mm_w, vx2))
        vy2 = max(0, min(mm_h, vy2))
        if vx2 > vx1 and vy2 > vy1:
            pygame.draw.rect(self.screen, COLOR_WHITE,
                             (mm_x + vx1, mm_y + vy1, vx2 - vx1, vy2 - vy1), 1)

        # Border
        pygame.draw.rect(self.screen, (100, 100, 100),
                         (mm_x - 1, mm_y - 1, mm_w + 2, mm_h + 2), 1)

"""High-fidelity tile renderer: brick walls, cobblestone floors, detailed sprites."""

import math
import pygame
import numpy as np
from config import (
    TILE_SIZE, TOKEN_RADIUS, TOKEN_BORDER,
    COLOR_BLACK, COLOR_WHITE, COLOR_PLAYER, COLOR_PLAYER_BORDER,
    COLOR_ENEMY, COLOR_ENEMY_BORDER, COLOR_NPC, COLOR_NPC_BORDER,
    COLOR_HP_GREEN, COLOR_HP_RED, COLOR_HP_BG,
    COLOR_GRID, COLOR_TRANSITION,
)
from fog_of_war import UNEXPLORED, EXPLORED, VISIBLE

TS = TILE_SIZE  # alias


# ======================================================================
# Tile sprite generators — each returns a pygame.Surface(TS, TS)
# ======================================================================

def _make_wall_tile(rng, neighbors):
    """Top-down wall: dark void with thin stone face on edges facing floors."""
    s = pygame.Surface((TS, TS))
    has_floor_n, has_floor_s, has_floor_w, has_floor_e = neighbors

    # Base: very dark void
    s.fill((6, 5, 4))

    # Deep interior wall — pure dark
    if not any(neighbors):
        for _ in range(2):
            rx = rng.integers(0, TS)
            ry = rng.integers(0, TS)
            pygame.draw.circle(s, (12, 10, 8), (rx, ry), 1)
        return s

    # Wall face thickness
    face = TS // 4
    stone_base = (85, 78, 65)
    stone_dark = (60, 54, 44)
    stone_light = (110, 102, 88)
    mortar = (50, 45, 38)
    cap_color = (75, 68, 56)

    # South-facing wall (floor is to the south = wall face on bottom edge)
    # This is the most visible — shows the wall "front face"
    if has_floor_s:
        fy = TS - face
        # Wall face with bricks
        pygame.draw.rect(s, stone_base, (0, fy, TS, face))
        # Brick rows
        brick_h = face // 2
        for row in range(2):
            by = fy + row * brick_h
            pygame.draw.line(s, mortar, (0, by), (TS, by), 1)
            brick_w = TS // 3
            offset = brick_w // 2 if row % 2 else 0
            for bx in range(offset, TS, brick_w):
                pygame.draw.line(s, mortar, (bx, by), (bx, by + brick_h), 1)
                # Brick shade
                shade = rng.integers(-8, 9)
                bc = tuple(max(0, min(255, c + shade)) for c in stone_base)
                bx1 = max(0, bx + 1)
                bx2 = min(TS, bx + brick_w - 1)
                if bx2 > bx1:
                    pygame.draw.rect(s, bc, (bx1, by + 1, bx2 - bx1, brick_h - 1))
        # Top cap (flat top of wall seen from above)
        pygame.draw.rect(s, cap_color, (0, fy - 2, TS, 3))
        pygame.draw.line(s, stone_light, (0, fy - 2), (TS, fy - 2), 1)
        # Bottom shadow cast onto floor
        shadow = pygame.Surface((TS, 3), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 60))
        s.blit(shadow, (0, TS - 3))

    # North-facing wall (floor is to the north = face on top edge)
    if has_floor_n:
        # Wall cap on top edge (you see the top of the wall from above)
        pygame.draw.rect(s, cap_color, (0, 0, TS, 3))
        pygame.draw.line(s, stone_light, (0, 0), (TS, 0), 1)
        # Thin face below cap
        pygame.draw.rect(s, stone_dark, (0, 3, TS, face // 2))
        pygame.draw.line(s, mortar, (0, 3 + face // 4), (TS, 3 + face // 4), 1)

    # West-facing wall (floor to the west = face on left edge)
    if has_floor_w:
        pygame.draw.rect(s, stone_base, (0, 0, face // 2, TS))
        # Vertical mortar
        pygame.draw.line(s, mortar, (face // 4, 0), (face // 4, TS), 1)
        # Right edge (inner side)
        pygame.draw.line(s, stone_dark, (face // 2, 0), (face // 2, TS), 1)
        # Left highlight
        pygame.draw.line(s, stone_light, (0, 0), (0, TS), 1)

    # East-facing wall (floor to the east = face on right edge)
    if has_floor_e:
        ex = TS - face // 2
        pygame.draw.rect(s, stone_base, (ex, 0, face // 2, TS))
        pygame.draw.line(s, mortar, (ex + face // 4, 0), (ex + face // 4, TS), 1)
        # Left edge (inner side)
        pygame.draw.line(s, stone_dark, (ex, 0), (ex, TS), 1)
        # Right edge highlight
        pygame.draw.line(s, stone_light, (TS - 1, 0), (TS - 1, TS), 1)

    return s


def _make_floor_tile(rng, is_room, theme_tint=None):
    """Cobblestone / flagstone floor with natural variation and optional tint."""
    s = pygame.Surface((TS, TS))

    if is_room:
        base_r, base_g, base_b = 180, 168, 145
    else:
        base_r, base_g, base_b = 150, 140, 122

    # Apply theme tint
    if theme_tint:
        tr, tg, tb = theme_tint
        base_r = (base_r * 2 + tr) // 3
        base_g = (base_g * 2 + tg) // 3
        base_b = (base_b * 2 + tb) // 3

    s.fill((base_r, base_g, base_b))

    # Flagstone pattern: irregular rectangles
    stones = []
    # Generate a few stone shapes within the tile
    num_stones = rng.integers(3, 6)
    for _ in range(num_stones):
        sx = rng.integers(0, TS - 6)
        sy = rng.integers(0, TS - 6)
        max_w = max(9, min(TS - sx, TS // 2 + 4))
        max_h = max(7, min(TS - sy, TS // 2 + 2))
        sw = rng.integers(8, max_w)
        sh = rng.integers(6, max_h)
        shade = rng.integers(-15, 16)
        color = (max(0, min(255, base_r + shade)),
                 max(0, min(255, base_g + shade)),
                 max(0, min(255, base_b + shade)))
        pygame.draw.rect(s, color, (sx, sy, sw, sh))
        # Stone edge (groove)
        groove = (max(0, base_r - 25), max(0, base_g - 25), max(0, base_b - 25))
        pygame.draw.rect(s, groove, (sx, sy, sw, sh), 1)

    # Subtle highlights on some stone surfaces
    for _ in range(rng.integers(0, 3)):
        hx = rng.integers(2, TS - 4)
        hy = rng.integers(2, TS - 4)
        hw = rng.integers(3, 8)
        highlight = pygame.Surface((hw, 2), pygame.SRCALPHA)
        highlight.fill((255, 255, 255, 18))
        s.blit(highlight, (hx, hy))

    # Small dirt/debris details
    for _ in range(rng.integers(0, 3)):
        dx = rng.integers(2, TS - 2)
        dy = rng.integers(2, TS - 2)
        dc = (max(0, base_r - 30 + rng.integers(-5, 6)),
              max(0, base_g - 30 + rng.integers(-5, 6)),
              max(0, base_b - 25 + rng.integers(-5, 6)))
        pygame.draw.circle(s, dc, (dx, dy), rng.integers(1, 3))

    return s


def _make_door_tile(rng, orientation="horizontal"):
    """Stone archway doorway — an opening in the wall."""
    s = _make_floor_tile(rng, True)  # floor base (you walk through it)

    arch_stone = (85, 78, 65)
    arch_dark = (55, 48, 40)
    arch_light = (105, 98, 82)
    threshold = (110, 95, 70)

    if orientation == "horizontal":
        # Walls are north+south, passage runs east-west
        # Draw arch pillars on top and bottom edges
        pillar_h = TS // 4
        # North pillar
        pygame.draw.rect(s, arch_stone, (0, 0, TS, pillar_h))
        pygame.draw.line(s, arch_light, (0, 0), (TS, 0), 1)
        pygame.draw.line(s, arch_dark, (0, pillar_h), (TS, pillar_h), 2)
        # Keystone detail
        pygame.draw.rect(s, arch_light, (TS // 2 - 4, 0, 8, pillar_h - 1))
        pygame.draw.rect(s, arch_dark, (TS // 2 - 4, 0, 8, pillar_h - 1), 1)
        # South pillar
        sy = TS - pillar_h
        pygame.draw.rect(s, arch_stone, (0, sy, TS, pillar_h))
        pygame.draw.line(s, arch_dark, (0, sy), (TS, sy), 2)
        pygame.draw.line(s, arch_light, (0, TS - 1), (TS, TS - 1), 1)
        pygame.draw.rect(s, arch_light, (TS // 2 - 4, sy + 1, 8, pillar_h - 1))
        pygame.draw.rect(s, arch_dark, (TS // 2 - 4, sy + 1, 8, pillar_h - 1), 1)
        # Threshold strip on floor
        pygame.draw.rect(s, threshold,
                         (2, pillar_h + 1, TS - 4, TS - pillar_h * 2 - 2))
    else:
        # Walls are east+west, passage runs north-south
        pillar_w = TS // 4
        # West pillar
        pygame.draw.rect(s, arch_stone, (0, 0, pillar_w, TS))
        pygame.draw.line(s, arch_light, (0, 0), (0, TS), 1)
        pygame.draw.line(s, arch_dark, (pillar_w, 0), (pillar_w, TS), 2)
        pygame.draw.rect(s, arch_light, (0, TS // 2 - 4, pillar_w - 1, 8))
        pygame.draw.rect(s, arch_dark, (0, TS // 2 - 4, pillar_w - 1, 8), 1)
        # East pillar
        ex = TS - pillar_w
        pygame.draw.rect(s, arch_stone, (ex, 0, pillar_w, TS))
        pygame.draw.line(s, arch_dark, (ex, 0), (ex, TS), 2)
        pygame.draw.line(s, arch_light, (TS - 1, 0), (TS - 1, TS), 1)
        pygame.draw.rect(s, arch_light, (ex + 1, TS // 2 - 4, pillar_w - 1, 8))
        pygame.draw.rect(s, arch_dark, (ex + 1, TS // 2 - 4, pillar_w - 1, 8), 1)
        # Threshold
        pygame.draw.rect(s, threshold,
                         (pillar_w + 1, 2, TS - pillar_w * 2 - 2, TS - 4))

    return s


# ======================================================================
# Entity sprite generators
# ======================================================================

def _draw_chest(surf, cx, cy, rng):
    """Detailed treasure chest."""
    w, h = 18, 14
    x, y = cx - w // 2, cy - h // 2
    wood = (160, 120, 40)
    wood_dark = (120, 85, 25)
    metal = (180, 170, 100)
    metal_dark = (140, 130, 70)

    # Body
    pygame.draw.rect(surf, wood, (x, y + 4, w, h - 4))
    pygame.draw.rect(surf, wood_dark, (x, y + 4, w, h - 4), 1)
    # Lid (slightly arched)
    pygame.draw.rect(surf, wood, (x, y, w, 6))
    pygame.draw.arc(surf, wood_dark, (x - 1, y - 2, w + 2, 10), 0, math.pi, 2)
    pygame.draw.rect(surf, wood_dark, (x, y, w, 6), 1)
    # Metal bands
    for by in [y + 2, y + h - 4]:
        pygame.draw.rect(surf, metal, (x + 1, by, w - 2, 2))
        pygame.draw.rect(surf, metal_dark, (x + 1, by, w - 2, 2), 1)
    # Lock
    pygame.draw.rect(surf, metal, (cx - 3, y + 3, 6, 5))
    pygame.draw.rect(surf, metal_dark, (cx - 3, y + 3, 6, 5), 1)
    pygame.draw.circle(surf, (50, 45, 35), (cx, y + 6), 1)


def _draw_barrel(surf, cx, cy, rng):
    """Wooden barrel with metal bands."""
    r = 10
    wood = (110, 78, 40)
    wood_light = (135, 100, 55)
    band = (90, 88, 82)
    band_dark = (65, 63, 58)

    # Body ellipse
    pygame.draw.ellipse(surf, wood, (cx - r, cy - r + 2, r * 2, r * 2 - 4))
    pygame.draw.ellipse(surf, (90, 62, 30), (cx - r, cy - r + 2, r * 2, r * 2 - 4), 1)
    # Stave lines
    for dx in [-r // 2, 0, r // 2]:
        pygame.draw.line(surf, (95, 65, 32),
                         (cx + dx, cy - r + 3), (cx + dx, cy + r - 3), 1)
    # Top ellipse
    pygame.draw.ellipse(surf, wood_light, (cx - r + 2, cy - r, r * 2 - 4, 6))
    pygame.draw.ellipse(surf, (90, 62, 30), (cx - r + 2, cy - r, r * 2 - 4, 6), 1)
    # Metal bands
    for by in [cy - r // 2, cy + r // 2 - 2]:
        pygame.draw.line(surf, band, (cx - r + 1, by), (cx + r - 1, by), 2)
        pygame.draw.line(surf, band_dark, (cx - r + 1, by + 2), (cx + r - 1, by + 2), 1)


def _draw_torch(surf, cx, cy, rng):
    """Wall torch with animated-looking flame and glow."""
    # Bracket
    bracket = (100, 95, 85)
    pygame.draw.rect(surf, bracket, (cx - 2, cy + 2, 4, 10))
    pygame.draw.rect(surf, (75, 70, 62), (cx - 3, cy + 10, 6, 3))
    # Stick
    pygame.draw.rect(surf, (90, 60, 25), (cx - 1, cy - 6, 3, 10))
    # Flame layers
    flame_colors = [(255, 200, 50), (255, 150, 30), (255, 100, 10)]
    for i, fc in enumerate(flame_colors):
        fr = 5 - i
        fy = cy - 8 - i * 2
        pygame.draw.ellipse(surf, fc, (cx - fr, fy, fr * 2, fr * 2 + 2))
    # Subtle warm glow
    glow = pygame.Surface((TS * 2, TS * 2), pygame.SRCALPHA)
    for gr in range(TS // 2, 0, -2):
        alpha = max(1, int(12 * (gr / (TS // 2))))
        pygame.draw.circle(glow, (255, 160, 40, alpha),
                           (TS, TS), gr)
    surf.blit(glow, (cx - TS, cy - TS))


def _draw_bones(surf, cx, cy, rng):
    """Bone pile."""
    bone = (200, 192, 170)
    bone_dark = (170, 160, 140)
    # Crossed bones
    pygame.draw.line(surf, bone, (cx - 7, cy - 5), (cx + 7, cy + 5), 2)
    pygame.draw.line(surf, bone, (cx + 7, cy - 5), (cx - 7, cy + 5), 2)
    # Bone ends (knobs)
    for dx, dy in [(-7, -5), (7, 5), (7, -5), (-7, 5)]:
        pygame.draw.circle(surf, bone, (cx + dx, cy + dy), 2)
        pygame.draw.circle(surf, bone_dark, (cx + dx, cy + dy), 2, 1)
    # Skull
    pygame.draw.circle(surf, bone, (cx, cy - 2), 4)
    pygame.draw.circle(surf, bone_dark, (cx, cy - 2), 4, 1)
    # Eye sockets
    pygame.draw.circle(surf, (40, 35, 30), (cx - 2, cy - 3), 1)
    pygame.draw.circle(surf, (40, 35, 30), (cx + 2, cy - 3), 1)


def _draw_cobweb(surf, cx, cy, rng):
    """Spider web in corner."""
    web = (200, 200, 200, 100)
    web_s = pygame.Surface((TS, TS), pygame.SRCALPHA)
    # Radial threads from corner
    ox, oy = 0, 0  # top-left corner
    for angle in range(0, 100, 15):
        rad = math.radians(angle)
        ex = int(ox + math.cos(rad) * TS * 0.8)
        ey = int(oy + math.sin(rad) * TS * 0.8)
        pygame.draw.line(web_s, web, (ox, oy), (ex, ey), 1)
    # Concentric arcs
    for r in range(TS // 4, TS, TS // 4):
        pygame.draw.arc(web_s, web, (-r, -r, r * 2, r * 2), 0, math.pi / 2, 1)
    surf.blit(web_s, (cx - TS // 2, cy - TS // 2))


def _draw_crate(surf, cx, cy, rng):
    """Wooden crate with cross-bracing."""
    s = 12
    wood = (130, 100, 55)
    wood_dark = (100, 75, 38)
    wood_light = (155, 125, 72)
    nail = (150, 150, 155)

    x, y = cx - s, cy - s
    w, h = s * 2, s * 2
    # Body
    pygame.draw.rect(surf, wood, (x, y, w, h))
    # Planks
    plank_w = w // 3
    for i in range(1, 3):
        px = x + i * plank_w
        pygame.draw.line(surf, wood_dark, (px, y), (px, y + h), 1)
    # Top/left highlight
    pygame.draw.line(surf, wood_light, (x, y), (x + w, y), 1)
    pygame.draw.line(surf, wood_light, (x, y), (x, y + h), 1)
    # Border
    pygame.draw.rect(surf, wood_dark, (x, y, w, h), 2)
    # Cross brace
    pygame.draw.line(surf, wood_dark, (x + 2, y + 2), (x + w - 2, y + h - 2), 2)
    pygame.draw.line(surf, wood_dark, (x + w - 2, y + 2), (x + 2, y + h - 2), 2)
    # Corner nails
    for nx, ny in [(x + 3, y + 3), (x + w - 3, y + 3),
                   (x + 3, y + h - 3), (x + w - 3, y + h - 3)]:
        pygame.draw.circle(surf, nail, (nx, ny), 1)


def _draw_table(surf, cx, cy, rng):
    """Wooden table."""
    tw, th = 20, 14
    wood = (125, 90, 50)
    wood_dark = (90, 65, 32)
    wood_light = (150, 115, 65)
    x, y = cx - tw // 2, cy - th // 2

    # Tabletop
    pygame.draw.rect(surf, wood, (x, y, tw, th))
    pygame.draw.rect(surf, wood_dark, (x, y, tw, th), 2)
    # Highlight
    pygame.draw.line(surf, wood_light, (x + 2, y + 1), (x + tw - 2, y + 1), 1)
    # Legs (visible corners)
    leg = (80, 55, 28)
    for lx, ly in [(x + 2, y + 2), (x + tw - 4, y + 2),
                   (x + 2, y + th - 4), (x + tw - 4, y + th - 4)]:
        pygame.draw.rect(surf, leg, (lx, ly, 3, 3))

    # Random item on table
    roll = rng.integers(0, 3)
    if roll == 0:
        # Candle
        pygame.draw.rect(surf, (220, 215, 195), (cx - 1, cy - 4, 3, 5))
        pygame.draw.circle(surf, (255, 200, 50), (cx, cy - 5), 2)
    elif roll == 1:
        # Plate
        pygame.draw.circle(surf, (180, 175, 165), (cx, cy), 4)
        pygame.draw.circle(surf, (160, 155, 145), (cx, cy), 4, 1)


def _draw_weapon_rack(surf, cx, cy, rng):
    """Wall-mounted weapon rack."""
    rack = (100, 75, 42)
    metal = (160, 160, 170)
    metal_dark = (120, 120, 130)
    wood = (110, 80, 40)

    # Back board
    pygame.draw.rect(surf, rack, (cx - 12, cy - 8, 24, 16))
    pygame.draw.rect(surf, (75, 55, 30), (cx - 12, cy - 8, 24, 16), 1)

    # Weapons
    # Sword
    pygame.draw.line(surf, metal, (cx - 7, cy - 6), (cx - 7, cy + 5), 2)
    pygame.draw.line(surf, metal_dark, (cx - 9, cy), (cx - 5, cy), 2)
    pygame.draw.rect(surf, wood, (cx - 8, cy + 4, 3, 3))

    # Axe
    pygame.draw.line(surf, wood, (cx + 2, cy - 6), (cx + 2, cy + 5), 2)
    pygame.draw.polygon(surf, metal, [(cx, cy - 5), (cx + 5, cy - 3), (cx, cy - 1)])
    pygame.draw.polygon(surf, metal_dark, [(cx, cy - 5), (cx + 5, cy - 3), (cx, cy - 1)], 1)

    # Spear tip
    pygame.draw.line(surf, wood, (cx + 9, cy - 6), (cx + 9, cy + 5), 1)
    pygame.draw.polygon(surf, metal, [(cx + 7, cy - 3), (cx + 9, cy - 7), (cx + 11, cy - 3)])


def _draw_bookshelf(surf, cx, cy, rng):
    """Bookshelf against wall."""
    shelf_w, shelf_h = 20, 18
    wood = (95, 70, 38)
    wood_dark = (70, 50, 25)
    x, y = cx - shelf_w // 2, cy - shelf_h // 2

    # Frame
    pygame.draw.rect(surf, wood, (x, y, shelf_w, shelf_h))
    pygame.draw.rect(surf, wood_dark, (x, y, shelf_w, shelf_h), 2)

    # Shelves (3 rows)
    row_h = shelf_h // 3
    for row in range(3):
        ry = y + row * row_h
        pygame.draw.line(surf, wood_dark, (x + 1, ry + row_h - 1),
                         (x + shelf_w - 1, ry + row_h - 1), 1)
        # Books
        bx = x + 2
        while bx < x + shelf_w - 3:
            bw = rng.integers(2, 5)
            bh = row_h - 3
            book_colors = [(140, 40, 40), (40, 80, 140), (40, 120, 60),
                           (130, 100, 50), (100, 50, 120), (50, 50, 50)]
            bc = book_colors[rng.integers(0, len(book_colors))]
            pygame.draw.rect(surf, bc, (bx, ry + 1, bw, bh))
            bx += bw + 1


def _draw_altar(surf, cx, cy, rng):
    """Stone altar/pedestal."""
    stone = (140, 135, 125)
    stone_dark = (100, 95, 88)
    stone_light = (170, 165, 155)

    # Base (wider)
    pygame.draw.rect(surf, stone_dark, (cx - 12, cy + 2, 24, 8))
    pygame.draw.rect(surf, (80, 75, 68), (cx - 12, cy + 2, 24, 8), 1)
    # Top slab
    pygame.draw.rect(surf, stone, (cx - 10, cy - 6, 20, 10))
    pygame.draw.rect(surf, stone_dark, (cx - 10, cy - 6, 20, 10), 1)
    pygame.draw.line(surf, stone_light, (cx - 9, cy - 5), (cx + 9, cy - 5), 1)
    # Glowing rune
    rune_colors = [(100, 200, 255), (200, 100, 255), (255, 200, 100)]
    rc = rune_colors[rng.integers(0, len(rune_colors))]
    pygame.draw.circle(surf, rc, (cx, cy - 1), 3)
    pygame.draw.circle(surf, (*rc, 60), (cx, cy - 1), 5)


def _draw_pit(surf, cx, cy, rng):
    """Dark pit/chasm in the floor."""
    r = TS // 3
    # Outer ring (crumbling edge)
    pygame.draw.circle(surf, (60, 55, 45), (cx, cy), r + 3)
    pygame.draw.circle(surf, (45, 40, 32), (cx, cy), r + 1)
    # Dark hole
    pygame.draw.circle(surf, (8, 6, 4), (cx, cy), r)
    # Depth shading
    pygame.draw.circle(surf, (15, 12, 10), (cx, cy), r - 2)
    # Edge highlight (rim)
    pygame.draw.arc(surf, (80, 72, 60),
                    (cx - r, cy - r, r * 2, r * 2),
                    math.pi * 0.8, math.pi * 1.8, 2)


def _draw_trap(surf, cx, cy, rng):
    """Pressure plate trap."""
    s = TS // 3
    stone = (120, 112, 98)
    stone_dark = (85, 78, 68)
    # Slightly recessed plate
    pygame.draw.rect(surf, stone_dark, (cx - s - 1, cy - s - 1, s * 2 + 2, s * 2 + 2))
    pygame.draw.rect(surf, stone, (cx - s, cy - s, s * 2, s * 2))
    # Grid pattern on plate
    for i in range(1, 3):
        pygame.draw.line(surf, stone_dark,
                         (cx - s + i * s * 2 // 3, cy - s),
                         (cx - s + i * s * 2 // 3, cy + s), 1)
        pygame.draw.line(surf, stone_dark,
                         (cx - s, cy - s + i * s * 2 // 3),
                         (cx + s, cy - s + i * s * 2 // 3), 1)
    # Highlight
    pygame.draw.line(surf, (140, 132, 118),
                     (cx - s + 1, cy - s + 1), (cx + s - 1, cy - s + 1), 1)


def _draw_cage(surf, cx, cy, rng):
    """Iron hanging cage."""
    metal = (100, 100, 110)
    metal_dark = (65, 65, 75)
    # Chain
    pygame.draw.line(surf, metal_dark, (cx, cy - 12), (cx, cy - 6), 2)
    # Cage frame
    r = 8
    pygame.draw.circle(surf, metal_dark, (cx, cy + 2), r, 2)
    # Bars
    for dx in [-5, -2, 2, 5]:
        pygame.draw.line(surf, metal, (cx + dx, cy - 5), (cx + dx, cy + 8), 1)
    # Bottom ring
    pygame.draw.ellipse(surf, metal_dark, (cx - 7, cy + 6, 14, 5), 1)


def _draw_chains(surf, cx, cy, rng):
    """Wall chains/shackles."""
    metal = (110, 108, 100)
    metal_dark = (75, 73, 68)
    # Wall plate
    pygame.draw.rect(surf, metal_dark, (cx - 3, cy - 10, 6, 4))
    pygame.draw.rect(surf, metal, (cx - 2, cy - 9, 4, 2))
    # Chain links (zigzag)
    for i in range(5):
        y = cy - 6 + i * 4
        x_off = 2 if i % 2 else -2
        pygame.draw.circle(surf, metal, (cx + x_off, y), 2)
        pygame.draw.circle(surf, metal_dark, (cx + x_off, y), 2, 1)
    # Shackle at bottom
    pygame.draw.arc(surf, metal, (cx - 5, cy + 10, 10, 8), 0, math.pi, 2)


def _draw_cauldron(surf, cx, cy, rng):
    """Bubbling cauldron."""
    iron = (55, 55, 60)
    iron_dark = (35, 35, 40)
    liquid = (50, 160, 50)
    liquid_light = (80, 200, 80)
    # Body
    r = 10
    pygame.draw.ellipse(surf, iron, (cx - r, cy - 4, r * 2, r + 6))
    pygame.draw.ellipse(surf, iron_dark, (cx - r, cy - 4, r * 2, r + 6), 2)
    # Rim
    pygame.draw.ellipse(surf, (80, 80, 85), (cx - r + 1, cy - 5, r * 2 - 2, 5))
    pygame.draw.ellipse(surf, iron_dark, (cx - r + 1, cy - 5, r * 2 - 2, 5), 1)
    # Liquid inside
    pygame.draw.ellipse(surf, liquid, (cx - r + 3, cy - 3, r * 2 - 6, 4))
    # Bubbles
    for _ in range(3):
        bx = cx + rng.integers(-6, 7)
        by = cy - 3 + rng.integers(-1, 2)
        pygame.draw.circle(surf, liquid_light, (bx, by), rng.integers(1, 3))
    # Legs
    for dx in [-7, 7]:
        pygame.draw.line(surf, iron_dark, (cx + dx, cy + r - 2),
                         (cx + dx + (2 if dx > 0 else -2), cy + r + 3), 2)


def _draw_iron_maiden(surf, cx, cy, rng):
    """Iron maiden torture device."""
    iron = (70, 68, 65)
    iron_dark = (45, 43, 40)
    iron_light = (95, 92, 88)
    # Body (coffin shape)
    points = [(cx - 8, cy - 10), (cx + 8, cy - 10),
              (cx + 10, cy + 4), (cx + 6, cy + 12),
              (cx - 6, cy + 12), (cx - 10, cy + 4)]
    pygame.draw.polygon(surf, iron, points)
    pygame.draw.polygon(surf, iron_dark, points, 2)
    # Center line (door)
    pygame.draw.line(surf, iron_dark, (cx, cy - 9), (cx, cy + 11), 1)
    # Spikes (inside visible)
    for sy in range(cy - 7, cy + 10, 4):
        pygame.draw.line(surf, (180, 40, 40), (cx - 2, sy), (cx + 2, sy), 1)
    # Hinges
    pygame.draw.rect(surf, iron_light, (cx - 9, cy - 6, 3, 3))
    pygame.draw.rect(surf, iron_light, (cx - 9, cy + 4, 3, 3))
    # Face silhouette
    pygame.draw.circle(surf, iron_dark, (cx, cy - 5), 4, 1)


def _draw_brazier(surf, cx, cy, rng):
    """Iron brazier with burning coals, orange glow, tripod legs."""
    iron = (70, 68, 65)
    iron_dark = (45, 43, 40)
    iron_light = (95, 92, 88)
    coal = (60, 20, 10)
    coal_hot = (220, 100, 20)
    ember = (255, 180, 40)

    # Tripod legs
    for dx in [-8, 0, 8]:
        lx = cx + dx
        pygame.draw.line(surf, iron_dark, (lx, cy + 4), (cx + dx + (dx // 2), cy + 12), 2)
    # Bowl body
    pygame.draw.ellipse(surf, iron, (cx - 9, cy - 2, 18, 10))
    pygame.draw.ellipse(surf, iron_dark, (cx - 9, cy - 2, 18, 10), 2)
    # Rim
    pygame.draw.ellipse(surf, iron_light, (cx - 9, cy - 3, 18, 5))
    pygame.draw.ellipse(surf, iron_dark, (cx - 9, cy - 3, 18, 5), 1)
    # Coals inside
    for _ in range(5):
        bx = cx + rng.integers(-6, 7)
        by = cy + rng.integers(-1, 3)
        c = coal_hot if rng.integers(0, 2) else coal
        pygame.draw.circle(surf, c, (bx, by), rng.integers(1, 3))
    # Embers
    for _ in range(3):
        ex = cx + rng.integers(-5, 6)
        ey = cy + rng.integers(-5, 0)
        pygame.draw.circle(surf, ember, (ex, ey), 1)
    # Warm glow
    glow = pygame.Surface((TS, TS), pygame.SRCALPHA)
    for gr in range(14, 0, -2):
        alpha = max(1, int(18 * (gr / 14)))
        pygame.draw.circle(glow, (255, 140, 30, alpha), (TS // 2, TS // 2 - 2), gr)
    surf.blit(glow, (cx - TS // 2, cy - TS // 2))


def _draw_shackles(surf, cx, cy, rng):
    """Wall-mounted iron shackles with chain, dangling open."""
    metal = (110, 108, 100)
    metal_dark = (75, 73, 68)
    metal_light = (140, 138, 130)

    # Wall plate (mounting bracket)
    pygame.draw.rect(surf, metal_dark, (cx - 4, cy - 12, 8, 5))
    pygame.draw.rect(surf, metal, (cx - 3, cy - 11, 6, 3))
    # Bolts
    pygame.draw.circle(surf, metal_light, (cx - 2, cy - 10), 1)
    pygame.draw.circle(surf, metal_light, (cx + 2, cy - 10), 1)
    # Chain links
    for i in range(4):
        y = cy - 7 + i * 3
        x_off = 1 if i % 2 else -1
        pygame.draw.circle(surf, metal, (cx + x_off, y), 2)
        pygame.draw.circle(surf, metal_dark, (cx + x_off, y), 2, 1)
    # Left shackle (open, dangling)
    sx = cx - 6
    sy = cy + 6
    pygame.draw.arc(surf, metal, (sx - 4, sy - 3, 8, 10), 0, math.pi, 2)
    pygame.draw.line(surf, metal_dark, (sx - 4, sy - 3), (sx - 4, sy + 1), 1)
    # Right shackle (open, dangling)
    sx2 = cx + 6
    pygame.draw.arc(surf, metal, (sx2 - 4, sy - 1, 8, 10), 0, math.pi, 2)
    pygame.draw.line(surf, metal_dark, (sx2 + 4, sy - 1), (sx2 + 4, sy + 3), 1)
    # Short chain segments connecting to shackles
    pygame.draw.line(surf, metal_dark, (cx - 1, cy + 4), (cx - 6, cy + 6), 1)
    pygame.draw.line(surf, metal_dark, (cx + 1, cy + 4), (cx + 6, cy + 5), 1)


def _draw_broken_pottery(surf, cx, cy, rng):
    """Scattered ceramic shards in brown/terracotta, 3-4 pieces."""
    terra = (175, 110, 60)
    terra_dark = (140, 80, 40)
    terra_light = (200, 140, 85)
    clay = (160, 100, 55)

    # 3-4 shards scattered around
    num_shards = rng.integers(3, 5)
    for i in range(num_shards):
        sx = cx + rng.integers(-9, 10)
        sy = cy + rng.integers(-6, 8)
        size = rng.integers(3, 6)
        c = terra if rng.integers(0, 2) else clay
        # Triangular shards
        p1 = (sx, sy)
        p2 = (sx + size, sy + rng.integers(-2, 3))
        p3 = (sx + rng.integers(-2, 3), sy + size)
        pygame.draw.polygon(surf, c, [p1, p2, p3])
        pygame.draw.polygon(surf, terra_dark, [p1, p2, p3], 1)
    # One larger curved piece (rim fragment)
    pygame.draw.arc(surf, terra_light, (cx - 5, cy - 3, 10, 8),
                    math.pi * 0.2, math.pi * 1.0, 2)
    pygame.draw.arc(surf, terra_dark, (cx - 5, cy - 3, 10, 8),
                    math.pi * 0.2, math.pi * 1.0, 1)
    # Dust/debris
    for _ in range(3):
        dx = cx + rng.integers(-8, 9)
        dy = cy + rng.integers(-5, 7)
        pygame.draw.circle(surf, (130, 110, 80), (dx, dy), 1)


def _draw_blood_trail(surf, cx, cy, rng):
    """Dark red splatters and streaks on the floor."""
    blood_s = pygame.Surface((TS, TS), pygame.SRCALPHA)
    blood = (120, 15, 15, 180)
    blood_dark = (80, 8, 8, 200)
    blood_light = (160, 30, 25, 140)

    # Main splatters (2-3)
    for _ in range(rng.integers(2, 4)):
        sx = TS // 2 + rng.integers(-8, 9)
        sy = TS // 2 + rng.integers(-8, 9)
        r = rng.integers(2, 5)
        pygame.draw.circle(blood_s, blood, (sx, sy), r)
        pygame.draw.circle(blood_s, blood_dark, (sx, sy), max(1, r - 1))
    # Streaks
    for _ in range(2):
        x1 = TS // 2 + rng.integers(-6, 7)
        y1 = TS // 2 + rng.integers(-6, 7)
        x2 = x1 + rng.integers(-8, 9)
        y2 = y1 + rng.integers(2, 8)
        pygame.draw.line(blood_s, blood_light, (x1, y1), (x2, y2), rng.integers(1, 3))
    # Small droplets
    for _ in range(5):
        dx = TS // 2 + rng.integers(-10, 11)
        dy = TS // 2 + rng.integers(-10, 11)
        pygame.draw.circle(blood_s, blood, (dx, dy), 1)
    surf.blit(blood_s, (cx - TS // 2, cy - TS // 2))


def _draw_glowing_fungus(surf, cx, cy, rng):
    """Bioluminescent mushrooms, blue-green glow, 2-3 clusters."""
    stem = (80, 120, 90)
    stem_dark = (50, 85, 60)
    cap_colors = [(40, 200, 180), (30, 180, 160), (60, 220, 200)]
    glow_color = (40, 200, 180)

    # Glow aura (underneath)
    glow = pygame.Surface((TS, TS), pygame.SRCALPHA)
    for gr in range(12, 0, -2):
        alpha = max(1, int(15 * (gr / 12)))
        pygame.draw.circle(glow, (*glow_color, alpha), (TS // 2, TS // 2), gr)
    surf.blit(glow, (cx - TS // 2, cy - TS // 2))

    # 2-3 mushroom clusters
    num = rng.integers(2, 4)
    positions = [(cx - 6, cy + 2), (cx + 5, cy - 1), (cx, cy + 6)]
    for i in range(num):
        mx, my = positions[i]
        h = rng.integers(5, 9)
        cap = cap_colors[i % len(cap_colors)]
        # Stem
        pygame.draw.line(surf, stem, (mx, my), (mx, my - h), 2)
        pygame.draw.line(surf, stem_dark, (mx - 1, my), (mx - 1, my - h), 1)
        # Cap (oval on top)
        cw = rng.integers(4, 7)
        pygame.draw.ellipse(surf, cap, (mx - cw // 2, my - h - 2, cw, 4))
        pygame.draw.ellipse(surf, stem_dark, (mx - cw // 2, my - h - 2, cw, 4), 1)
        # Bright spot on cap
        pygame.draw.circle(surf, (150, 255, 240), (mx, my - h - 1), 1)


def _draw_coin_pile(surf, cx, cy, rng):
    """Small pile of gold/silver coins with sparkle."""
    gold = (220, 190, 50)
    gold_dark = (180, 150, 30)
    gold_light = (255, 230, 100)
    silver = (190, 190, 200)
    silver_dark = (150, 150, 160)

    # Pile base (ellipse shadow)
    pygame.draw.ellipse(surf, (80, 70, 30), (cx - 8, cy - 2, 16, 10))
    # Scattered coins (bottom layer)
    for _ in range(6):
        bx = cx + rng.integers(-6, 7)
        by = cy + rng.integers(-1, 5)
        is_gold = rng.integers(0, 3) > 0  # mostly gold
        c = gold if is_gold else silver
        cd = gold_dark if is_gold else silver_dark
        pygame.draw.ellipse(surf, c, (bx - 2, by - 1, 5, 3))
        pygame.draw.ellipse(surf, cd, (bx - 2, by - 1, 5, 3), 1)
    # Top coins (visible)
    for _ in range(3):
        tx = cx + rng.integers(-4, 5)
        ty = cy + rng.integers(-3, 2)
        pygame.draw.ellipse(surf, gold, (tx - 2, ty - 1, 5, 3))
        pygame.draw.ellipse(surf, gold_dark, (tx - 2, ty - 1, 5, 3), 1)
    # Sparkle
    sx = cx + rng.integers(-3, 4)
    sy = cy + rng.integers(-2, 2)
    pygame.draw.line(surf, gold_light, (sx - 2, sy), (sx + 2, sy), 1)
    pygame.draw.line(surf, gold_light, (sx, sy - 2), (sx, sy + 2), 1)


def _draw_potion(surf, cx, cy, rng):
    """Glass bottle with colored liquid (random color), cork top."""
    glass = (200, 220, 230)
    glass_dark = (150, 170, 180)
    cork = (160, 130, 80)
    cork_dark = (130, 100, 60)
    liquid_options = [(180, 40, 40), (40, 120, 200), (50, 180, 60),
                      (180, 50, 180), (200, 180, 40)]
    liquid = liquid_options[rng.integers(0, len(liquid_options))]
    liquid_dark = tuple(max(0, c - 40) for c in liquid)

    # Bottle body
    pygame.draw.ellipse(surf, glass, (cx - 5, cy - 2, 10, 12))
    pygame.draw.ellipse(surf, glass_dark, (cx - 5, cy - 2, 10, 12), 1)
    # Liquid inside (lower portion)
    pygame.draw.ellipse(surf, liquid, (cx - 4, cy + 2, 8, 7))
    pygame.draw.ellipse(surf, liquid_dark, (cx - 4, cy + 2, 8, 7), 1)
    # Neck
    pygame.draw.rect(surf, glass, (cx - 2, cy - 6, 4, 6))
    pygame.draw.line(surf, glass_dark, (cx - 2, cy - 6), (cx - 2, cy - 1), 1)
    pygame.draw.line(surf, glass_dark, (cx + 2, cy - 6), (cx + 2, cy - 1), 1)
    # Cork
    pygame.draw.rect(surf, cork, (cx - 2, cy - 9, 5, 4))
    pygame.draw.rect(surf, cork_dark, (cx - 2, cy - 9, 5, 4), 1)
    # Glass highlight
    pygame.draw.line(surf, (240, 250, 255), (cx - 3, cy + 1), (cx - 3, cy + 6), 1)


def _draw_scroll(surf, cx, cy, rng):
    """Rolled parchment with ribbon tie."""
    parch = (220, 205, 170)
    parch_dark = (190, 175, 140)
    parch_light = (240, 225, 195)
    ribbon = (140, 40, 40)
    ribbon_dark = (100, 25, 25)

    # Main rolled body (horizontal cylinder)
    pygame.draw.rect(surf, parch, (cx - 10, cy - 4, 20, 8))
    pygame.draw.rect(surf, parch_dark, (cx - 10, cy - 4, 20, 8), 1)
    # Top highlight (cylinder shading)
    pygame.draw.line(surf, parch_light, (cx - 9, cy - 3), (cx + 9, cy - 3), 1)
    # Bottom shadow
    pygame.draw.line(surf, parch_dark, (cx - 9, cy + 3), (cx + 9, cy + 3), 1)
    # Roll ends (circles at each end)
    for dx in [-10, 10]:
        pygame.draw.circle(surf, parch, (cx + dx, cy), 4)
        pygame.draw.circle(surf, parch_dark, (cx + dx, cy), 4, 1)
        pygame.draw.circle(surf, parch_light, (cx + dx, cy - 1), 1)
    # Ribbon tie in the middle
    pygame.draw.rect(surf, ribbon, (cx - 2, cy - 5, 4, 10))
    pygame.draw.rect(surf, ribbon_dark, (cx - 2, cy - 5, 4, 10), 1)
    # Ribbon bow/tails
    pygame.draw.line(surf, ribbon, (cx - 2, cy + 5), (cx - 4, cy + 8), 2)
    pygame.draw.line(surf, ribbon, (cx + 2, cy + 5), (cx + 4, cy + 8), 2)


def _draw_tapestry(surf, cx, cy, rng):
    """Hanging wall tapestry with faded pattern, tattered bottom edge."""
    fabric_colors = [(120, 40, 50), (45, 60, 110), (50, 90, 50)]
    fc = fabric_colors[rng.integers(0, len(fabric_colors))]
    fabric_dark = tuple(max(0, c - 30) for c in fc)
    fabric_light = tuple(min(255, c + 30) for c in fc)
    fringe = tuple(max(0, c - 15) for c in fc)
    rod = (110, 85, 50)
    rod_dark = (80, 60, 35)

    # Hanging rod
    pygame.draw.line(surf, rod, (cx - 10, cy - 12), (cx + 10, cy - 12), 2)
    pygame.draw.circle(surf, rod_dark, (cx - 10, cy - 12), 2)
    pygame.draw.circle(surf, rod_dark, (cx + 10, cy - 12), 2)
    # Main fabric body
    pygame.draw.rect(surf, fc, (cx - 9, cy - 10, 18, 18))
    pygame.draw.rect(surf, fabric_dark, (cx - 9, cy - 10, 18, 18), 1)
    # Faded pattern (simple geometric)
    pygame.draw.rect(surf, fabric_light, (cx - 6, cy - 7, 12, 12), 1)
    pygame.draw.line(surf, fabric_light, (cx - 6, cy - 1), (cx + 6, cy - 1), 1)
    pygame.draw.line(surf, fabric_light, (cx, cy - 7), (cx, cy + 5), 1)
    # Diamond motif in center
    diamond = [(cx, cy - 5), (cx + 4, cy - 1), (cx, cy + 3), (cx - 4, cy - 1)]
    pygame.draw.polygon(surf, fabric_dark, diamond, 1)
    # Tattered bottom edge (irregular)
    for tx in range(cx - 9, cx + 9, 3):
        tear_y = cy + 8 + rng.integers(-2, 3)
        pygame.draw.line(surf, fringe, (tx, cy + 8), (tx, tear_y), 1)


def _draw_bed(surf, cx, cy, rng):
    """Simple wooden frame bed with mattress and pillow."""
    wood = (100, 72, 38)
    wood_dark = (72, 50, 25)
    mattress = (140, 130, 110)
    mattress_dark = (115, 105, 88)
    sheet = (170, 165, 155)
    pillow = (185, 180, 168)
    pillow_dark = (160, 155, 142)

    bw, bh = 22, 14
    x, y = cx - bw // 2, cy - bh // 2

    # Wooden frame
    pygame.draw.rect(surf, wood, (x, y, bw, bh))
    pygame.draw.rect(surf, wood_dark, (x, y, bw, bh), 2)
    # Frame legs (corners)
    for lx, ly in [(x, y), (x + bw - 2, y), (x, y + bh - 2), (x + bw - 2, y + bh - 2)]:
        pygame.draw.rect(surf, wood_dark, (lx, ly, 3, 3))
    # Mattress
    pygame.draw.rect(surf, mattress, (x + 2, y + 2, bw - 4, bh - 4))
    pygame.draw.rect(surf, mattress_dark, (x + 2, y + 2, bw - 4, bh - 4), 1)
    # Sheet (covers lower half)
    pygame.draw.rect(surf, sheet, (x + 3, cy, bw - 6, bh // 2 - 3))
    pygame.draw.line(surf, mattress_dark, (x + 3, cy), (x + bw - 3, cy), 1)
    # Pillow at top
    pygame.draw.ellipse(surf, pillow, (x + 3, y + 2, 8, 5))
    pygame.draw.ellipse(surf, pillow_dark, (x + 3, y + 2, 8, 5), 1)
    # Pillow indent
    pygame.draw.ellipse(surf, pillow_dark, (x + 5, y + 3, 4, 3), 1)


def _draw_bench(surf, cx, cy, rng):
    """Stone or wooden bench, simple rectangle with legs."""
    stone = (130, 125, 115)
    stone_dark = (95, 90, 82)
    stone_light = (155, 150, 140)

    bw, bh = 20, 6
    x, y = cx - bw // 2, cy - bh // 2

    # Seat slab
    pygame.draw.rect(surf, stone, (x, y, bw, bh))
    pygame.draw.rect(surf, stone_dark, (x, y, bw, bh), 1)
    # Top highlight
    pygame.draw.line(surf, stone_light, (x + 1, y + 1), (x + bw - 1, y + 1), 1)
    # Legs (two thick supports)
    leg_w, leg_h = 4, 6
    pygame.draw.rect(surf, stone_dark, (x + 2, y + bh, leg_w, leg_h))
    pygame.draw.rect(surf, (80, 75, 68), (x + 2, y + bh, leg_w, leg_h), 1)
    pygame.draw.rect(surf, stone_dark, (x + bw - leg_w - 2, y + bh, leg_w, leg_h))
    pygame.draw.rect(surf, (80, 75, 68), (x + bw - leg_w - 2, y + bh, leg_w, leg_h), 1)
    # Wear marks
    for _ in range(2):
        wx = x + rng.integers(3, bw - 3)
        pygame.draw.line(surf, stone_dark, (wx, y + 2), (wx + 2, y + 2), 1)


def _draw_spike_trap(surf, cx, cy, rng):
    """Open pit showing metal spikes below, with crumbling edges."""
    pit_dark = (10, 8, 6)
    pit_mid = (25, 20, 15)
    edge = (90, 82, 68)
    edge_dark = (60, 55, 44)
    spike = (160, 160, 170)
    spike_dark = (120, 120, 130)

    r = 10
    # Crumbling edge (rough outer)
    for _ in range(12):
        ax = cx + rng.integers(-r - 2, r + 3)
        ay = cy + rng.integers(-r - 2, r + 3)
        pygame.draw.circle(surf, edge, (ax, ay), rng.integers(2, 4))
    # Pit hole
    pygame.draw.rect(surf, pit_dark, (cx - r, cy - r, r * 2, r * 2))
    pygame.draw.rect(surf, pit_mid, (cx - r + 1, cy - r + 1, r * 2 - 2, r * 2 - 2), 1)
    # Depth shading on inner walls
    pygame.draw.line(surf, (40, 35, 25), (cx - r + 1, cy - r + 1),
                     (cx + r - 1, cy - r + 1), 1)
    # Spikes (pointing up from bottom)
    for sx in range(cx - 7, cx + 8, 4):
        # Spike triangle
        pts = [(sx, cy + r - 3), (sx - 2, cy + r - 1), (sx + 2, cy + r - 1)]
        pygame.draw.polygon(surf, spike, pts)
        pygame.draw.polygon(surf, spike_dark, pts, 1)
        # Spike tip highlight
        pygame.draw.circle(surf, (200, 200, 210), (sx, cy + r - 3), 1)
    # Edge rim
    pygame.draw.rect(surf, edge_dark, (cx - r, cy - r, r * 2, r * 2), 2)
    # Crumble details
    for _ in range(4):
        rx = cx + rng.integers(-r, r + 1)
        ry = cy + rng.integers(-r, r + 1)
        pygame.draw.circle(surf, edge, (rx, ry), 1)


def _draw_web(surf, cx, cy, rng):
    """Large spider web spanning most of the tile, radial + spiral pattern."""
    web_s = pygame.Surface((TS, TS), pygame.SRCALPHA)
    web = (200, 200, 200, 90)
    web_bright = (220, 220, 220, 120)
    center_x, center_y = TS // 2, TS // 2
    radius = TS // 2 - 3

    # Radial threads (8 spokes)
    num_spokes = 8
    for i in range(num_spokes):
        angle = (2 * math.pi * i) / num_spokes
        ex = int(center_x + math.cos(angle) * radius)
        ey = int(center_y + math.sin(angle) * radius)
        pygame.draw.line(web_s, web, (center_x, center_y), (ex, ey), 1)

    # Spiral threads (concentric rings connecting spokes)
    for r in range(4, radius, 4):
        for i in range(num_spokes):
            a1 = (2 * math.pi * i) / num_spokes
            a2 = (2 * math.pi * (i + 1)) / num_spokes
            x1 = int(center_x + math.cos(a1) * r)
            y1 = int(center_y + math.sin(a1) * r)
            x2 = int(center_x + math.cos(a2) * (r + 1))
            y2 = int(center_y + math.sin(a2) * (r + 1))
            pygame.draw.line(web_s, web, (x1, y1), (x2, y2), 1)

    # Center hub (brighter)
    pygame.draw.circle(web_s, web_bright, (center_x, center_y), 2)

    # A few dew drops (bright dots)
    for _ in range(3):
        da = rng.random() * 2 * math.pi
        dr = rng.integers(4, radius)
        dx = int(center_x + math.cos(da) * dr)
        dy = int(center_y + math.sin(da) * dr)
        pygame.draw.circle(web_s, (230, 230, 255, 160), (dx, dy), 1)

    surf.blit(web_s, (cx - TS // 2, cy - TS // 2))


def _draw_rubble(surf, cx, cy, rng):
    """Pile of broken stone blocks, dust, fallen masonry."""
    stone = (130, 125, 112)
    stone_dark = (90, 85, 75)
    stone_light = (160, 155, 142)
    dust = (110, 105, 90)

    # Dust base
    pygame.draw.ellipse(surf, dust, (cx - 10, cy - 4, 20, 14))
    # Rubble pieces (larger blocks at bottom, smaller on top)
    blocks = []
    for _ in range(5):
        bx = cx + rng.integers(-8, 6)
        by = cy + rng.integers(-3, 6)
        bw = rng.integers(4, 8)
        bh = rng.integers(3, 6)
        blocks.append((bx, by, bw, bh))
    for bx, by, bw, bh in blocks:
        shade = rng.integers(-12, 13)
        c = tuple(max(0, min(255, v + shade)) for v in stone)
        pygame.draw.rect(surf, c, (bx, by, bw, bh))
        pygame.draw.rect(surf, stone_dark, (bx, by, bw, bh), 1)
    # Top highlight on a few blocks
    for bx, by, bw, bh in blocks[:2]:
        pygame.draw.line(surf, stone_light, (bx + 1, by + 1), (bx + bw - 1, by + 1), 1)
    # Small debris
    for _ in range(6):
        dx = cx + rng.integers(-9, 10)
        dy = cy + rng.integers(-5, 8)
        pygame.draw.circle(surf, stone_dark, (dx, dy), 1)
    # Dust particles
    for _ in range(3):
        px = cx + rng.integers(-7, 8)
        py = cy + rng.integers(-3, 5)
        pygame.draw.circle(surf, (140, 135, 120), (px, py), 1)


def _draw_sarcophagus(surf, cx, cy, rng):
    """Stone coffin with carved lid, slightly ajar showing dark interior."""
    stone = (140, 135, 125)
    stone_dark = (100, 95, 85)
    stone_light = (170, 165, 155)
    interior = (15, 12, 10)

    sw, sh = 22, 12
    x, y = cx - sw // 2, cy - sh // 2

    # Base (slightly wider)
    pygame.draw.rect(surf, stone_dark, (x - 1, y + 1, sw + 2, sh))
    pygame.draw.rect(surf, (80, 75, 68), (x - 1, y + 1, sw + 2, sh), 1)
    # Lid (slightly offset to show gap)
    lid_offset = 3
    pygame.draw.rect(surf, stone, (x + lid_offset, y - 2, sw - 2, sh))
    pygame.draw.rect(surf, stone_dark, (x + lid_offset, y - 2, sw - 2, sh), 1)
    # Lid top highlight
    pygame.draw.line(surf, stone_light, (x + lid_offset + 1, y - 1),
                     (x + lid_offset + sw - 3, y - 1), 1)
    # Carved cross on lid
    mid_x = cx + lid_offset // 2
    pygame.draw.line(surf, stone_dark, (mid_x, y), (mid_x, y + sh - 3), 1)
    pygame.draw.line(surf, stone_dark, (mid_x - 4, y + 3), (mid_x + 4, y + 3), 1)
    # Dark interior visible in gap
    pygame.draw.rect(surf, interior, (x, y, lid_offset + 1, sh - 1))
    # Rim detail at head and foot
    pygame.draw.rect(surf, stone_light, (x + lid_offset, y - 2, 3, sh), 1)
    pygame.draw.rect(surf, stone_light, (x + sw - 1, y - 2, 3, sh), 1)


def _draw_pillar(surf, cx, cy, rng):
    """Stone pillar."""
    stone = (150, 145, 135)
    stone_dark = (110, 105, 95)
    stone_light = (180, 175, 165)
    # Base (wider)
    pygame.draw.circle(surf, stone_dark, (cx, cy + 2), 8)
    # Shaft
    pygame.draw.circle(surf, stone, (cx, cy), 7)
    # Top cap
    pygame.draw.circle(surf, stone_light, (cx, cy - 1), 5)
    pygame.draw.circle(surf, stone_dark, (cx, cy - 1), 5, 1)
    # Highlight
    pygame.draw.circle(surf, (200, 195, 185), (cx - 2, cy - 2), 2)


def _draw_fountain(surf, cx, cy, rng):
    """Stone fountain with water."""
    stone = (140, 135, 125)
    stone_dark = (100, 95, 85)
    water = (60, 120, 190)
    water_light = (100, 160, 220)
    # Outer basin
    r = 12
    pygame.draw.circle(surf, stone_dark, (cx, cy), r)
    pygame.draw.circle(surf, stone, (cx, cy), r - 1)
    pygame.draw.circle(surf, stone_dark, (cx, cy), r, 2)
    # Water inside
    pygame.draw.circle(surf, water, (cx, cy), r - 3)
    # Water highlights
    for _ in range(4):
        hx = cx + rng.integers(-6, 7)
        hy = cy + rng.integers(-6, 7)
        pygame.draw.circle(surf, water_light, (hx, hy), 1)
    # Center column
    pygame.draw.circle(surf, stone, (cx, cy), 3)
    pygame.draw.circle(surf, stone_dark, (cx, cy), 3, 1)
    # Splash
    pygame.draw.circle(surf, water_light, (cx, cy - 1), 2)


def _draw_statue(surf, cx, cy, rng):
    """Stone statue on pedestal."""
    stone = (130, 128, 120)
    stone_dark = (90, 88, 80)
    stone_light = (160, 158, 148)
    # Pedestal
    pygame.draw.rect(surf, stone_dark, (cx - 8, cy + 4, 16, 8))
    pygame.draw.rect(surf, stone, (cx - 7, cy + 5, 14, 6))
    pygame.draw.line(surf, stone_light, (cx - 7, cy + 5), (cx + 7, cy + 5), 1)
    # Figure (simplified humanoid from above)
    # Torso
    pygame.draw.ellipse(surf, stone, (cx - 5, cy - 8, 10, 12))
    pygame.draw.ellipse(surf, stone_dark, (cx - 5, cy - 8, 10, 12), 1)
    # Head
    pygame.draw.circle(surf, stone_light, (cx, cy - 10), 4)
    pygame.draw.circle(surf, stone_dark, (cx, cy - 10), 4, 1)
    # Shadow
    pygame.draw.ellipse(surf, (0, 0, 0, 30), (cx - 6, cy + 8, 12, 4))


def _draw_armor_stand(surf, cx, cy, rng):
    """Armor stand with plate armor."""
    wood = (110, 80, 50)
    metal = (160, 155, 145)
    dark = (100, 95, 85)
    pygame.draw.line(surf, wood, (cx, cy + 12), (cx, cy - 8), 2)
    pygame.draw.line(surf, wood, (cx - 6, cy + 12), (cx + 6, cy + 12), 2)
    pygame.draw.ellipse(surf, metal, (cx - 6, cy - 6, 12, 14))
    pygame.draw.ellipse(surf, dark, (cx - 6, cy - 6, 12, 14), 1)
    pygame.draw.circle(surf, metal, (cx, cy - 8), 4)
    pygame.draw.circle(surf, dark, (cx, cy - 8), 4, 1)

def _draw_shield_display(surf, cx, cy, rng):
    """Shield mounted on wall."""
    wood = (120, 90, 55)
    metal = (140, 140, 130)
    pygame.draw.rect(surf, wood, (cx - 3, cy - 10, 6, 20))
    pygame.draw.polygon(surf, metal, [(cx, cy - 8), (cx - 7, cy - 2), (cx - 5, cy + 7), (cx, cy + 10), (cx + 5, cy + 7), (cx + 7, cy - 2)])
    pygame.draw.polygon(surf, (100, 100, 90), [(cx, cy - 8), (cx - 7, cy - 2), (cx - 5, cy + 7), (cx, cy + 10), (cx + 5, cy + 7), (cx + 7, cy - 2)], 1)
    pygame.draw.line(surf, (180, 50, 50), (cx - 3, cy - 4), (cx + 3, cy + 4), 2)

def _draw_banner(surf, cx, cy, rng):
    """Hanging banner/flag."""
    rod = (130, 100, 60)
    colors = [(140, 30, 30), (30, 30, 140), (30, 100, 30), (120, 90, 30)]
    color = colors[rng.integers(0, len(colors))]
    pygame.draw.line(surf, rod, (cx - 8, cy - 12), (cx + 8, cy - 12), 2)
    pygame.draw.polygon(surf, color, [(cx - 6, cy - 11), (cx + 6, cy - 11), (cx + 4, cy + 8), (cx, cy + 12), (cx - 4, cy + 8)])
    dark = tuple(max(0, c - 40) for c in color)
    pygame.draw.polygon(surf, dark, [(cx - 6, cy - 11), (cx + 6, cy - 11), (cx + 4, cy + 8), (cx, cy + 12), (cx - 4, cy + 8)], 1)

def _draw_bunk_bed(surf, cx, cy, rng):
    """Bunk bed from above."""
    wood = (120, 85, 50)
    dark = (80, 55, 30)
    blanket = (100, 80, 60)
    pygame.draw.rect(surf, dark, (cx - 6, cy - 10, 12, 20))
    pygame.draw.rect(surf, wood, (cx - 5, cy - 9, 10, 18))
    pygame.draw.rect(surf, blanket, (cx - 4, cy - 7, 8, 7))
    pygame.draw.rect(surf, (blanket[0] - 15, blanket[1] - 15, blanket[2] - 10), (cx - 4, cy + 3, 8, 7))
    pygame.draw.line(surf, dark, (cx - 5, cy), (cx + 5, cy), 1)

def _draw_footlocker(surf, cx, cy, rng):
    """Small footlocker/trunk."""
    wood = (100, 75, 45)
    metal = (130, 125, 115)
    pygame.draw.rect(surf, wood, (cx - 5, cy - 3, 10, 6))
    pygame.draw.rect(surf, (70, 50, 30), (cx - 5, cy - 3, 10, 6), 1)
    pygame.draw.line(surf, metal, (cx - 5, cy), (cx + 5, cy), 1)
    pygame.draw.rect(surf, metal, (cx - 1, cy - 1, 2, 2))

def _draw_grindstone(surf, cx, cy, rng):
    """Sharpening wheel."""
    stone = (140, 138, 130)
    wood = (110, 80, 50)
    pygame.draw.line(surf, wood, (cx - 6, cy + 4), (cx + 6, cy + 4), 2)
    pygame.draw.circle(surf, stone, (cx, cy), 6)
    pygame.draw.circle(surf, (110, 108, 100), (cx, cy), 6, 1)
    pygame.draw.circle(surf, (170, 168, 160), (cx - 1, cy - 1), 2)

def _draw_lantern(surf, cx, cy, rng):
    """Hanging lantern (similar to torch but smaller glow)."""
    metal = (130, 125, 110)
    glow = (255, 200, 80)
    pygame.draw.rect(surf, metal, (cx - 3, cy - 5, 6, 8))
    pygame.draw.rect(surf, (90, 85, 70), (cx - 3, cy - 5, 6, 8), 1)
    pygame.draw.rect(surf, glow, (cx - 2, cy - 3, 4, 4))
    pygame.draw.circle(surf, (255, 220, 120, 60), (cx, cy), 8)

def _draw_trophy_pile(surf, cx, cy, rng):
    """Pile of trophies/skulls."""
    bone = (200, 190, 170)
    dark = (140, 130, 110)
    for i in range(4):
        ox = rng.integers(-6, 7)
        oy = rng.integers(-4, 5)
        pygame.draw.circle(surf, bone, (cx + ox, cy + oy), 3)
        pygame.draw.circle(surf, dark, (cx + ox, cy + oy), 3, 1)
        pygame.draw.circle(surf, (40, 40, 40), (cx + ox - 1, cy + oy), 1)
        pygame.draw.circle(surf, (40, 40, 40), (cx + ox + 1, cy + oy), 1)

def _draw_gate(surf, cx, cy, rng):
    """Iron gate/portcullis."""
    metal = (100, 95, 85)
    dark = (60, 55, 45)
    for dx in range(-8, 9, 4):
        pygame.draw.line(surf, metal, (cx + dx, cy - 12), (cx + dx, cy + 12), 2)
    for dy in range(-8, 9, 8):
        pygame.draw.line(surf, dark, (cx - 10, cy + dy), (cx + 10, cy + dy), 1)

def _draw_guard_alcove(surf, cx, cy, rng):
    """Small alcove niche."""
    stone = (120, 115, 105)
    dark = (80, 75, 65)
    pygame.draw.rect(surf, dark, (cx - 6, cy - 6, 12, 12))
    pygame.draw.rect(surf, stone, (cx - 5, cy - 5, 10, 10))
    pygame.draw.rect(surf, dark, (cx - 5, cy - 5, 10, 10), 1)


ENTITY_DRAWERS = {
    "chest": _draw_chest,
    "barrel": _draw_barrel,
    "torch": _draw_torch,
    "bones": _draw_bones,
    "cobweb": _draw_cobweb,
    "crate": _draw_crate,
    "table": _draw_table,
    "weapon_rack": _draw_weapon_rack,
    "bookshelf": _draw_bookshelf,
    "altar": _draw_altar,
    "pit": _draw_pit,
    "trap": _draw_trap,
    "cage": _draw_cage,
    "chains": _draw_chains,
    "cauldron": _draw_cauldron,
    "iron_maiden": _draw_iron_maiden,
    "brazier": _draw_brazier,
    "shackles": _draw_shackles,
    "broken_pottery": _draw_broken_pottery,
    "blood_trail": _draw_blood_trail,
    "glowing_fungus": _draw_glowing_fungus,
    "coin_pile": _draw_coin_pile,
    "potion": _draw_potion,
    "scroll": _draw_scroll,
    "tapestry": _draw_tapestry,
    "bed": _draw_bed,
    "bench": _draw_bench,
    "spike_trap": _draw_spike_trap,
    "web": _draw_web,
    "rubble": _draw_rubble,
    "sarcophagus": _draw_sarcophagus,
    "pillar": _draw_pillar,
    "fountain": _draw_fountain,
    "statue": _draw_statue,
    "armor_stand": _draw_armor_stand,
    "shield_display": _draw_shield_display,
    "banner": _draw_banner,
    "bunk_bed": _draw_bunk_bed,
    "footlocker": _draw_footlocker,
    "grindstone": _draw_grindstone,
    "lantern": _draw_lantern,
    "trophy_pile": _draw_trophy_pile,
    "gate": _draw_gate,
    "guard_alcove": _draw_guard_alcove,
}


# Room themes: (name, drawers, floor_tint)
# ~1/3 monster/combat, ~1/3 trap/puzzle, ~1/3 atmospheric dressing
ROOM_THEMES = [
    # -- Monster/combat rooms --
    ("torture", [_draw_iron_maiden, _draw_chains, _draw_shackles, _draw_blood_trail, _draw_cage],
     (155, 115, 110)),
    ("crypt", [_draw_sarcophagus, _draw_bones, _draw_cobweb, _draw_altar, _draw_brazier],
     (125, 130, 150)),
    ("boss_lair", [_draw_altar, _draw_brazier, _draw_pillar, _draw_tapestry, _draw_statue, _draw_coin_pile],
     (145, 120, 130)),
    ("spider_den", [_draw_web, _draw_cobweb, _draw_bones, _draw_glowing_fungus],
     (130, 135, 130)),
    ("guard_post", [_draw_weapon_rack, _draw_bench, _draw_brazier, _draw_barrel],
     (150, 140, 128)),

    # -- Trap/puzzle rooms --
    ("trapped_hall", [_draw_spike_trap, _draw_broken_pottery, _draw_blood_trail, _draw_rubble],
     (150, 135, 125)),
    ("alchemy_lab", [_draw_cauldron, _draw_bookshelf, _draw_potion, _draw_scroll, _draw_table],
     (130, 150, 130)),
    ("shrine", [_draw_altar, _draw_pillar, _draw_statue, _draw_fountain, _draw_brazier],
     (135, 135, 160)),
    ("ritual", [_draw_altar, _draw_blood_trail, _draw_brazier, _draw_tapestry, _draw_sarcophagus],
     (140, 125, 140)),

    # -- Atmospheric/dressing --
    ("barracks", [_draw_bed, _draw_table, _draw_bench, _draw_barrel, _draw_shackles],
     (155, 145, 130)),
    ("library", [_draw_bookshelf, _draw_table, _draw_scroll, _draw_cobweb, _draw_pillar],
     (140, 132, 118)),
    ("storage", [_draw_barrel, _draw_crate, _draw_broken_pottery, _draw_rubble],
     (152, 142, 122)),
    ("common_room", [_draw_table, _draw_bench, _draw_barrel, _draw_bed, _draw_brazier],
     (165, 155, 138)),
    ("prison", [_draw_cage, _draw_chains, _draw_shackles, _draw_bones, _draw_blood_trail],
     (142, 128, 122)),
    ("armory", [_draw_weapon_rack, _draw_crate, _draw_barrel, _draw_chest, _draw_bench],
     (148, 142, 128)),
    ("treasure", [_draw_chest, _draw_coin_pile, _draw_potion, _draw_scroll, _draw_pillar],
     (160, 150, 125)),
    ("abandoned", [_draw_rubble, _draw_broken_pottery, _draw_cobweb, _draw_glowing_fungus, _draw_bones],
     (135, 135, 135)),
    ("safe_haven", [_draw_fountain, _draw_bench, _draw_brazier, _draw_table, _draw_bed],
     (170, 162, 148)),
]

# Corridor dressing (sparse atmospheric details)
CORRIDOR_DRESSING = [
    _draw_broken_pottery, _draw_rubble, _draw_blood_trail,
    _draw_glowing_fungus, _draw_cobweb, _draw_bones,
]


# ======================================================================
# Main Renderer
# ======================================================================

class Renderer:
    """High-fidelity tile renderer with pre-rendered level surfaces."""

    def __init__(self, screen: pygame.Surface, game_map):
        self.screen = screen
        self.game_map = game_map
        self.show_grid = False
        self._font_cache = {}

        self._level_surfaces: dict[int, pygame.Surface] = {}
        for z in game_map.z_levels:
            self._level_surfaces[z] = self._prerender_level(z)

    def _prerender_level(self, z: int) -> pygame.Surface:
        gm = self.game_map
        w, h = gm.width, gm.height
        rng = np.random.default_rng(hash(z) + 54321)

        surf = pygame.Surface((w * TS, h * TS))
        surf.fill((6, 5, 4))

        walk = gm.walkability.get(z)
        if walk is None:
            return surf

        # Room mask
        room_mask = np.zeros((h, w), dtype=bool)
        entities = gm.entities.get(z, [])
        for e in entities:
            if e.get("type") == "room":
                rx, ry = e["x"], e["y"]
                rw, rh = e["w"], e["h"]
                room_mask[max(0, ry):min(h, ry + rh),
                          max(0, rx):min(w, rx + rw)] = True

        # Detect doorways: walkable tile at room-to-corridor transition
        # Must have walls on opposite sides AND cross a room boundary
        door_tiles = set()
        for ty in range(1, h - 1):
            for tx in range(1, w - 1):
                if not walk[ty, tx]:
                    continue
                n = walk[ty - 1, tx]
                s_val = walk[ty + 1, tx]
                ww = walk[ty, tx - 1]
                e = walk[ty, tx + 1]

                # Horizontal passage (walls N+S, open E+W)
                if not n and not s_val and ww and e:
                    # Must be at room boundary: one side in room, other not
                    rm_w = room_mask[ty, tx - 1] if tx > 0 else False
                    rm_e = room_mask[ty, tx + 1] if tx < w - 1 else False
                    rm_here = room_mask[ty, tx]
                    if (rm_w != rm_e) or (rm_here != rm_w) or (rm_here != rm_e):
                        door_tiles.add((tx, ty, "horizontal"))

                # Vertical passage (walls W+E, open N+S)
                elif not ww and not e and n and s_val:
                    rm_n = room_mask[ty - 1, tx] if ty > 0 else False
                    rm_s = room_mask[ty + 1, tx] if ty < h - 1 else False
                    rm_here = room_mask[ty, tx]
                    if (rm_n != rm_s) or (rm_here != rm_n) or (rm_here != rm_s):
                        door_tiles.add((tx, ty, "vertical"))

        # Build per-room theme tint map
        rooms_data = self._find_rooms(room_mask, walk, w, h)
        tint_map = {}  # (tx, ty) -> tint color
        room_themes = {}  # room_index -> (name, drawers, tint)

        # Map pipeline room purposes to theme tints
        _PURPOSE_TINTS = {
            "entrance":       (155, 155, 145),
            "boss_lair":      (145, 120, 130),
            "guard_room":     (150, 140, 128),
            "barracks":       (155, 145, 130),
            "armory":         (148, 142, 128),
            "storage":        (152, 142, 122),
            "cell":           (142, 128, 122),
            "shrine":         (135, 135, 160),
            "alchemy_lab":    (130, 150, 130),
            "library":        (140, 132, 118),
            "crypt":          (125, 130, 150),
            "treasure_vault": (160, 150, 125),
            "safe_haven":     (170, 162, 148),
            "common_room":    (165, 155, 138),
            "secret_chamber": (140, 125, 140),
        }

        # Try to match pipeline rooms to geometric rooms by overlap
        pipeline_rooms = {}
        for e in entities:
            if e.get("type") == "room" and e.get("variant") == "graph_room":
                purpose = e.get("purpose") or (e.get("metadata", {}) or {}).get("purpose")
                # Also check the zone field in metadata
                if not purpose:
                    name = e.get("name") or (e.get("metadata", {}) or {}).get("name", "")
                    purpose = name  # node_id might hint at purpose
                pipeline_rooms[(e.get("x", 0), e.get("y", 0))] = e

        for room_idx, (room_tiles, wall_adj, center_tiles) in enumerate(rooms_data):
            # Try to find pipeline purpose for this geometric room
            tint = None
            if room_tiles and pipeline_rooms:
                # Sample a tile from this room and find which pipeline room contains it
                sample_tx, sample_ty = next(iter(room_tiles))
                for (rx, ry), pe in pipeline_rooms.items():
                    pw, ph = pe.get("w", 0), pe.get("h", 0)
                    if rx <= sample_tx < rx + pw and ry <= sample_ty < ry + ph:
                        purpose = pe.get("purpose") or (pe.get("metadata", {}) or {}).get("purpose", "")
                        tint = _PURPOSE_TINTS.get(purpose)
                        # Also find matching ROOM_THEMES entry for furniture
                        for t in ROOM_THEMES:
                            if t[0] == purpose or t[0] in purpose:
                                room_themes[room_idx] = t
                                break
                        break

            if tint is None:
                theme = ROOM_THEMES[rng.integers(0, len(ROOM_THEMES))]
                room_themes[room_idx] = theme
                tint = theme[2]
            elif room_idx not in room_themes:
                theme = ROOM_THEMES[rng.integers(0, len(ROOM_THEMES))]
                room_themes[room_idx] = theme

            for tx, ty in room_tiles:
                tint_map[(tx, ty)] = tint

        # 1. Draw all tiles
        for ty in range(h):
            for tx in range(w):
                px, py = tx * TS, ty * TS
                if walk[ty, tx]:
                    h_door = (tx, ty, "horizontal") in door_tiles
                    v_door = (tx, ty, "vertical") in door_tiles
                    if h_door:
                        tile = _make_door_tile(rng, "horizontal")
                    elif v_door:
                        tile = _make_door_tile(rng, "vertical")
                    else:
                        tint = tint_map.get((tx, ty))
                        tile = _make_floor_tile(rng, room_mask[ty, tx], tint)
                    surf.blit(tile, (px, py))
                else:
                    neighbors = (
                        ty > 0 and walk[ty - 1, tx],      # N
                        ty < h - 1 and walk[ty + 1, tx],  # S
                        tx > 0 and walk[ty, tx - 1],      # W
                        tx < w - 1 and walk[ty, tx + 1],  # E
                    )
                    tile = _make_wall_tile(rng, neighbors)
                    surf.blit(tile, (px, py))

        # 2. Entity sprites — curated placement, not random scatter
        self._place_curated_entities(surf, entities, walk, room_mask, w, h, rng,
                                     rooms_data, room_themes)

        # 3. Building labels
        buildings = [e for e in entities if e.get("type") == "building"]
        self._draw_building_labels(surf, buildings)

        # 4. Transitions
        for tr in gm.transitions:
            if tr["from_z"] == z:
                self._draw_transition(surf, tr)

        return surf

    def _place_curated_entities(self, surf, entities, walk, room_mask, w, h, rng,
                                rooms_data=None, room_themes=None):
        """Place a curated subset of entities with logical positioning."""
        # Check if pipeline dressing is present — if so, use it exclusively
        pipeline_dressing = [e for e in entities if e.get("type") == "dressing"]
        pipeline_doors = [e for e in entities if e.get("type") == "door"]
        has_pipeline_data = len(pipeline_dressing) > 0

        if has_pipeline_data:
            self._place_pipeline_entities(surf, entities, walk, room_mask, w, h, rng)
            return

        # Legacy path: categorize entities for old curated system
        by_type = {}
        for e in entities:
            t = e.get("type", "")
            if t in ENTITY_DRAWERS:
                by_type.setdefault(t, []).append(e)

        # Find wall-adjacent floor tiles (for torches)
        wall_adjacent = set()
        for ty in range(1, h - 1):
            for tx in range(1, w - 1):
                if not walk[ty, tx]:
                    continue
                for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    ny, nx = ty + dy, tx + dx
                    if 0 <= ny < h and 0 <= nx < w and not walk[ny, nx]:
                        wall_adjacent.add((tx, ty))
                        break

        # Find room corners (for chests)
        room_corners = set()
        for ty in range(1, h - 1):
            for tx in range(1, w - 1):
                if not room_mask[ty, tx] or not walk[ty, tx]:
                    continue
                # Corner = walkable with walls on two adjacent sides
                adj_walls = sum(1 for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]
                                if not walk[ty + dy, tx + dx])
                if adj_walls >= 2:
                    room_corners.add((tx, ty))

        placed = set()  # (tx, ty) -> prevent overlap

        def _try_place(drawer, tx, ty):
            if (tx, ty) in placed:
                return False
            # Don't place too close to other entities
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    if (tx + dx, ty + dy) in placed:
                        return False
            placed.add((tx, ty))
            cx = tx * TS + TS // 2
            cy = ty * TS + TS // 2
            drawer(surf, cx, cy, rng)
            return True

        # Torches: place on wall-adjacent tiles, spaced out, ~1 per 8 tiles
        wall_list = sorted(wall_adjacent)
        rng.shuffle(wall_list)
        torch_count = max(4, len(wall_list) // 12)
        placed_torches = 0
        for tx, ty in wall_list:
            if placed_torches >= torch_count:
                break
            # Ensure spacing from other torches (at least 6 tiles apart)
            too_close = False
            for ptx, pty in placed:
                if abs(ptx - tx) + abs(pty - ty) < 6:
                    too_close = True
                    break
            if too_close:
                continue
            if _try_place(_draw_torch, tx, ty):
                placed_torches += 1

        # Chests: place in room corners, max 1-2 per room area
        corner_list = sorted(room_corners)
        rng.shuffle(corner_list)
        chest_count = min(len(corner_list), max(3, len(corner_list) // 6))
        placed_chests = 0
        for tx, ty in corner_list:
            if placed_chests >= chest_count:
                break
            if _try_place(_draw_chest, tx, ty):
                placed_chests += 1

        # Barrels/crates: place along walls in rooms, limited count
        wall_room_tiles = [(tx, ty) for tx, ty in wall_adjacent
                           if room_mask[ty, tx]]
        rng.shuffle(wall_room_tiles)
        barrel_crate_count = min(len(wall_room_tiles), max(4, len(wall_room_tiles) // 10))
        placed_bc = 0
        for tx, ty in wall_room_tiles:
            if placed_bc >= barrel_crate_count:
                break
            drawer = _draw_barrel if rng.random() < 0.5 else _draw_crate
            if _try_place(drawer, tx, ty):
                placed_bc += 1

        # Bones: sparse, in corridors (not rooms), rare
        corridor_tiles = [(tx, ty) for tx, ty in wall_adjacent
                          if not room_mask[ty, tx]]
        rng.shuffle(corridor_tiles)
        bones_count = min(len(corridor_tiles), max(2, len(corridor_tiles) // 20))
        placed_bones = 0
        for tx, ty in corridor_tiles:
            if placed_bones >= bones_count:
                break
            if _try_place(_draw_bones, tx, ty):
                placed_bones += 1

        # Cobwebs: in room corners, very sparse
        rng.shuffle(corner_list)
        cobweb_count = min(len(corner_list), max(1, len(corner_list) // 12))
        placed_cw = 0
        for tx, ty in corner_list:
            if placed_cw >= cobweb_count:
                break
            if _try_place(_draw_cobweb, tx, ty):
                placed_cw += 1

        # Themed room furniture
        if rooms_data is None:
            rooms_data = self._find_rooms(room_mask, walk, w, h)
        if room_themes is None:
            room_themes = {}
            for i in range(len(rooms_data)):
                room_themes[i] = ROOM_THEMES[rng.integers(0, len(ROOM_THEMES))]

        for room_idx, (room_tiles, wall_tiles, center_tiles) in enumerate(rooms_data):
            theme = room_themes.get(room_idx, ROOM_THEMES[0])
            theme_name, theme_drawers = theme[0], theme[1]

            # Place 3-6 objects per room from the theme
            obj_count = min(len(room_tiles) // 6, rng.integers(3, 7))

            # Shuffle available tiles
            candidates = list(center_tiles) + list(wall_tiles)
            rng.shuffle(candidates)

            placed_in_room = 0
            for tx, ty in candidates:
                if placed_in_room >= obj_count:
                    break
                drawer = theme_drawers[rng.integers(0, len(theme_drawers))]
                if _try_place(drawer, tx, ty):
                    placed_in_room += 1

        # Pits: in corridors, rare
        corridor_interior = [(tx, ty) for tx, ty in wall_adjacent
                             if not room_mask[ty, tx]
                             and all(walk[ty + dy, tx + dx]
                                     for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]
                                     if 0 <= ty + dy < h and 0 <= tx + dx < w)]
        rng.shuffle(corridor_interior)
        pit_count = max(1, len(corridor_interior) // 30)
        placed_pits = 0
        for tx, ty in corridor_interior:
            if placed_pits >= pit_count:
                break
            if _try_place(_draw_pit, tx, ty):
                placed_pits += 1

        # Traps: scattered in corridors
        corridor_floor = [(tx, ty) for ty in range(1, h - 1)
                          for tx in range(1, w - 1)
                          if walk[ty, tx] and not room_mask[ty, tx]
                          and (tx, ty) not in placed]
        rng.shuffle(corridor_floor)
        trap_count = max(2, len(corridor_floor) // 40)
        placed_traps = 0
        for tx, ty in corridor_floor:
            if placed_traps >= trap_count:
                break
            if _try_place(_draw_trap, tx, ty):
                placed_traps += 1

        # Corridor atmospheric dressing: sparse clutter
        rng.shuffle(corridor_floor)
        dressing_count = max(3, len(corridor_floor) // 20)
        placed_dressing = 0
        for tx, ty in corridor_floor:
            if placed_dressing >= dressing_count:
                break
            drawer = CORRIDOR_DRESSING[rng.integers(0, len(CORRIDOR_DRESSING))]
            if _try_place(drawer, tx, ty):
                placed_dressing += 1

    def _place_pipeline_entities(self, surf, entities, walk, room_mask, w, h, rng):
        """Draw entities from the generation pipeline (dressing, doors, traps)."""
        placed = set()

        def _try_place(drawer, tx, ty):
            if (tx, ty) in placed or tx < 0 or ty < 0 or tx >= w or ty >= h:
                return False
            placed.add((tx, ty))
            cx = tx * TS + TS // 2
            cy = ty * TS + TS // 2
            drawer(surf, cx, cy, rng)
            return True

        # 1. Draw all pipeline dressing entities at their positions
        for e in entities:
            if e.get("type") != "dressing":
                continue
            variant = e.get("variant", "")
            tx, ty = e.get("x", 0), e.get("y", 0)
            if variant in ENTITY_DRAWERS:
                _try_place(ENTITY_DRAWERS[variant], tx, ty)

        # 2. Draw doors
        for e in entities:
            if e.get("type") != "door":
                continue
            tx, ty = e.get("x", 0), e.get("y", 0)
            if 0 <= tx < w and 0 <= ty < h and (tx, ty) not in placed:
                cx = tx * TS + TS // 2
                cy = ty * TS + TS // 2
                stone = (130, 120, 100)
                dark = (80, 70, 55)
                pygame.draw.rect(surf, dark, (cx - 12, cy - 14, 24, 28))
                pygame.draw.rect(surf, stone, (cx - 10, cy - 12, 20, 24))
                pygame.draw.rect(surf, (90, 85, 70), (cx - 6, cy - 8, 12, 20))
                placed.add((tx, ty))

        # 3. Add torches on walls (supplement pipeline dressing for atmosphere)
        wall_adjacent = []
        for ty in range(1, h - 1):
            for tx in range(1, w - 1):
                if not walk[ty, tx]:
                    continue
                for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    ny, nx = ty + dy, tx + dx
                    if 0 <= ny < h and 0 <= nx < w and not walk[ny, nx]:
                        wall_adjacent.append((tx, ty))
                        break

        rng.shuffle(wall_adjacent)
        torch_count = max(6, len(wall_adjacent) // 10)
        placed_torches = 0
        for tx, ty in wall_adjacent:
            if placed_torches >= torch_count:
                break
            too_close = any(abs(ptx - tx) + abs(pty - ty) < 6 for ptx, pty in placed)
            if not too_close:
                _try_place(_draw_torch, tx, ty)
                placed_torches += 1

        # 4. Add bones/cobwebs in corridors for atmosphere
        corridor_tiles = [(tx, ty) for tx, ty in wall_adjacent if not room_mask[ty, tx]]
        rng.shuffle(corridor_tiles)
        for i, (tx, ty) in enumerate(corridor_tiles[:max(3, len(corridor_tiles) // 15)]):
            drawer = _draw_bones if rng.random() < 0.5 else _draw_cobweb
            _try_place(drawer, tx, ty)

    def _find_rooms(self, room_mask, walk, w, h):
        """Find individual rooms via flood fill and classify tiles."""
        visited = np.zeros((h, w), dtype=bool)
        rooms = []

        for start_y in range(h):
            for start_x in range(w):
                if visited[start_y, start_x] or not room_mask[start_y, start_x]:
                    continue

                # Flood fill this room
                room_tiles = set()
                wall_adj = set()
                center_tiles = set()
                stack = [(start_x, start_y)]

                while stack:
                    tx, ty = stack.pop()
                    if visited[ty, tx] or not room_mask[ty, tx]:
                        continue
                    visited[ty, tx] = True

                    if not walk[ty, tx]:
                        continue
                    room_tiles.add((tx, ty))

                    is_wall_adj = False
                    is_interior = True
                    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        ny, nx = ty + dy, tx + dx
                        if 0 <= ny < h and 0 <= nx < w:
                            if room_mask[ny, nx] and not visited[ny, nx]:
                                stack.append((nx, ny))
                            if not walk[ny, nx]:
                                is_wall_adj = True
                                is_interior = False
                        else:
                            is_interior = False

                    if is_wall_adj:
                        wall_adj.add((tx, ty))
                    if is_interior:
                        center_tiles.add((tx, ty))

                if len(room_tiles) >= 4:
                    rooms.append((room_tiles, wall_adj, center_tiles))

        return rooms

    def _draw_building_labels(self, surf, buildings):
        font = self._get_font(max(12, TS // 2))
        for b in buildings:
            x, y = b["x"], b["y"]
            bw = b["w"]
            meta = b.get("metadata", {})
            name = meta.get("name",
                            b.get("variant", "Building").replace("_", " ").title())
            cx = x * TS + bw * TS // 2
            cy = y * TS - TS // 2

            label = font.render(name, True, (230, 220, 190))
            lw, lh = label.get_size()
            bg = pygame.Surface((lw + 10, lh + 6), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 180))
            pygame.draw.rect(bg, (160, 130, 60, 220),
                             (0, 0, lw + 10, lh + 6), 1)
            surf.blit(bg, (cx - lw // 2 - 5, cy - lh // 2 - 3))
            surf.blit(label, (cx - lw // 2, cy - lh // 2))

    def _draw_transition(self, surf, transition):
        tx, ty = transition["x"], transition["y"]
        t_type = transition.get("type", "stairs")
        to_z = transition.get("to_z", "?")
        px, py = tx * TS, ty * TS
        cx, cy = px + TS // 2, py + TS // 2

        # Glow
        glow = pygame.Surface((TS * 4, TS * 4), pygame.SRCALPHA)
        for r in range(TS * 2, 0, -3):
            alpha = max(1, int(40 * (r / (TS * 2))))
            pygame.draw.circle(glow, (*COLOR_TRANSITION, alpha),
                               (TS * 2, TS * 2), r)
        surf.blit(glow, (cx - TS * 2, cy - TS * 2))

        # Tile background
        color = (170, 140, 240) if "up" in t_type else (140, 110, 210)
        marker = pygame.Surface((TS, TS), pygame.SRCALPHA)
        marker.fill((*color, 160))
        pygame.draw.rect(marker, (*color, 255), (0, 0, TS, TS), 2)
        surf.blit(marker, (px, py))

        # Stair steps
        steps = 5
        step_h = (TS - 4) // steps
        for i in range(steps):
            sy = py + 2 + i * step_h
            indent = 3 + i * 2 if "down" in t_type else 3 + (steps - 1 - i) * 2
            indent = min(indent, TS // 2 - 2)
            pygame.draw.line(surf, COLOR_WHITE,
                             (px + indent, sy), (px + TS - indent, sy), 2)

        # Label
        font = self._get_font(max(10, TS // 3))
        text = f"{'Up' if 'up' in t_type else 'Down'} z{to_z}"
        label = font.render(text, True, COLOR_WHITE)
        lw, lh = label.get_size()
        bg = pygame.Surface((lw + 8, lh + 4), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 200))
        pygame.draw.rect(bg, (*COLOR_TRANSITION, 220),
                         (0, 0, lw + 8, lh + 4), 1)
        surf.blit(bg, (cx - lw // 2 - 4, py - lh - 8))
        surf.blit(label, (cx - lw // 2, py - lh - 6))

    # ==================================================================
    # Per-frame rendering
    # ==================================================================

    def render(self, camera, creatures, fog, player_z: int, engine):
        self.screen.fill(COLOR_BLACK)
        z_levels = self.game_map.z_levels
        if player_z - 1 in z_levels:
            self._draw_level(camera, player_z - 1, dimmed=True, z_offset=-1)
        self._draw_level(camera, player_z, dimmed=False, z_offset=0)
        self._draw_creatures(camera, creatures, fog, player_z)
        self._draw_fog(camera, fog, player_z)
        if self.show_grid:
            self._draw_grid(camera, player_z)

    def _draw_level(self, camera, z, dimmed, z_offset):
        level_surf = self._level_surfaces.get(z)
        if level_surf is None:
            return
        full_w, full_h = level_surf.get_size()
        sw, sh = self.screen.get_size()
        w_tl_x, w_tl_y = camera.screen_to_world(0, 0)
        w_br_x, w_br_y = camera.screen_to_world(sw, sh)
        src_x = max(0, int(w_tl_x))
        src_y = max(0, int(w_tl_y))
        src_x2 = min(full_w, int(w_br_x) + 1)
        src_y2 = min(full_h, int(w_br_y) + 1)
        if src_x2 <= src_x or src_y2 <= src_y:
            return
        src_rect = pygame.Rect(src_x, src_y, src_x2 - src_x, src_y2 - src_y)
        clip = level_surf.subsurface(src_rect)
        dst_w = int(src_rect.width * camera.zoom)
        dst_h = int(src_rect.height * camera.zoom)
        if dst_w <= 0 or dst_h <= 0:
            return
        if camera.zoom >= 1.0:
            scaled = pygame.transform.scale(clip, (dst_w, dst_h))
        else:
            scaled = pygame.transform.smoothscale(clip, (dst_w, dst_h))
        if dimmed:
            scaled.set_alpha(100)
        sx, sy = camera.world_to_screen(float(src_x), float(src_y), z_offset)
        self.screen.blit(scaled, (int(sx), int(sy)))

    def _draw_creatures(self, camera, creatures, fog, player_z):
        for c in creatures:
            if not c.alive or c.z != player_z:
                continue
            if fog.enabled:
                state = fog.get_state(c.x, c.y, c.z)
                if state == UNEXPLORED:
                    continue
                if state == EXPLORED and c.token_type == "enemy":
                    continue
            c.visible = fog.is_visible(c.x, c.y, c.z)

            wx = c.x * TS + TS / 2
            wy = c.y * TS + TS / 2
            sx, sy = camera.world_to_screen(wx, wy)
            sx, sy = int(sx), int(sy)

            radius = max(5, int(TOKEN_RADIUS * camera.zoom))
            border = max(1, int(TOKEN_BORDER * camera.zoom))

            if c.token_type == "player":
                fill, outline = COLOR_PLAYER, COLOR_PLAYER_BORDER
            elif c.token_type == "enemy":
                fill, outline = COLOR_ENEMY, COLOR_ENEMY_BORDER
            else:
                fill, outline = COLOR_NPC, COLOR_NPC_BORDER

            # Shadow
            shadow = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(shadow, (0, 0, 0, 80),
                               (radius + 2, radius + 2), radius)
            self.screen.blit(shadow, (sx - radius, sy - radius + 2))

            # Token
            pygame.draw.circle(self.screen, fill, (sx, sy), radius)
            pygame.draw.circle(self.screen, outline, (sx, sy), radius, border)

            # Letter
            font = self._get_font(max(12, int(16 * camera.zoom)))
            letter = c.name[0].upper() if c.name else "?"
            text = font.render(letter, True, COLOR_WHITE)
            self.screen.blit(text, text.get_rect(center=(sx, sy)))

            # Name
            if camera.zoom >= 0.6:
                nf = self._get_font(max(10, int(11 * camera.zoom)))
                ns = nf.render(c.name, True, outline)
                nr = ns.get_rect(center=(sx, sy + radius + 12))
                nbg = pygame.Surface(
                    (ns.get_width() + 6, ns.get_height() + 4), pygame.SRCALPHA)
                nbg.fill((0, 0, 0, 160))
                self.screen.blit(nbg, (nr.x - 3, nr.y - 2))
                self.screen.blit(ns, nr)

            # HP bar
            if c.hp < c.max_hp:
                bw = int(TS * camera.zoom * 1.0)
                bh = max(3, int(5 * camera.zoom))
                bx = sx - bw // 2
                by = sy - radius - bh - 4
                pygame.draw.rect(self.screen, COLOR_HP_BG,
                                 (bx - 1, by - 1, bw + 2, bh + 2))
                fw = int(bw * c.hp_pct)
                hc = COLOR_HP_GREEN if c.hp_pct > 0.5 else COLOR_HP_RED
                pygame.draw.rect(self.screen, hc, (bx, by, fw, bh))

    def _draw_fog(self, camera, fog, player_z):
        if not fog.enabled:
            return
        fog_arr = fog._fog.get(player_z)
        if fog_arr is None:
            return
        h, w = fog_arr.shape
        x1, y1, x2, y2 = camera.visible_tile_range()
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        tile_px = max(1, int(TS * camera.zoom))
        fog_black = pygame.Surface((tile_px, tile_px), pygame.SRCALPHA)
        fog_black.fill((0, 0, 0, 255))
        fog_dim = pygame.Surface((tile_px, tile_px), pygame.SRCALPHA)
        fog_dim.fill((0, 0, 0, 130))

        for ty in range(y1, y2):
            for tx in range(x1, x2):
                state = fog_arr[ty, tx]
                if state == VISIBLE:
                    continue
                sx, sy = camera.world_to_screen(tx * TS, ty * TS)
                pos = (int(sx), int(sy))
                if state == UNEXPLORED:
                    self.screen.blit(fog_black, pos)
                elif state == EXPLORED:
                    self.screen.blit(fog_dim, pos)

    def _draw_grid(self, camera, player_z):
        x1, y1, x2, y2 = camera.visible_tile_range()
        mw, mh = self.game_map.width, self.game_map.height
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(mw, x2), min(mh, y2)
        color = COLOR_GRID
        for tx in range(x1, x2 + 1):
            sx, sy_top = camera.world_to_screen(tx * TS, y1 * TS)
            _, sy_bot = camera.world_to_screen(tx * TS, y2 * TS)
            pygame.draw.line(self.screen, color,
                             (int(sx), int(sy_top)), (int(sx), int(sy_bot)), 1)
        for ty in range(y1, y2 + 1):
            sx_l, sy = camera.world_to_screen(x1 * TS, ty * TS)
            sx_r, _ = camera.world_to_screen(x2 * TS, ty * TS)
            pygame.draw.line(self.screen, color,
                             (int(sx_l), int(sy)), (int(sx_r), int(sy)), 1)

    def _get_font(self, size):
        if size not in self._font_cache:
            try:
                self._font_cache[size] = pygame.font.SysFont(
                    "consolas", size, bold=True)
            except Exception:
                self._font_cache[size] = pygame.font.Font(None, size)
        return self._font_cache[size]

    def toggle_grid(self):
        self.show_grid = not self.show_grid

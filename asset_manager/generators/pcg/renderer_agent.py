"""
RendererAgent -- Composites all layers into final PNG output.
Draws terrain, water overlay, roads, structures, assets, labels,
compass rose, legend, title banner, and atmospheric vignette.
"""

import json
import numpy as np
from .base_agent import BaseAgent
from asset_manager.shared_state import SharedState
from typing import Any
from PIL import Image, ImageDraw, ImageFont
import os

try:
    from agents.sprite_manager import SpriteManager, composite_sprites
    _SPRITES_AVAILABLE = True
except ImportError:
    _SPRITES_AVAILABLE = False


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try multiple font paths (Windows then Linux) and fall back to default."""
    candidates = []
    if bold:
        candidates = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
    else:
        candidates = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


class RendererAgent(BaseAgent):
    name = "RendererAgent"

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        output_format = params.get("format", "png")
        output_path = params.get("output_path", "./output/generated_map.png")
        show_labels = params.get("show_labels", True)
        show_grid = params.get("show_grid", False)
        show_legend = params.get("show_legend", True)

        h, w = shared_state.config.height, shared_state.config.width

        # ---- Title banner height -----------------------------------
        title_label = None
        for lb in shared_state.labels:
            if lb.category == "title":
                title_label = lb
                break

        font_title = _load_font(max(16, w // 28), bold=True)
        banner_h = 0
        if title_label is not None:
            # Measure text height for banner
            tmp = Image.new("RGBA", (1, 1))
            tmp_d = ImageDraw.Draw(tmp)
            bbox = tmp_d.textbbox((0, 0), title_label.text, font=font_title)
            text_h = bbox[3] - bbox[1]
            banner_h = text_h + 20  # 10 px padding top + bottom

        total_h = h + banner_h

        # ---- Create RGBA canvas ------------------------------------
        canvas = Image.new("RGBA", (w, total_h), (0, 0, 0, 255))

        # Paste terrain into the map region (below the banner)
        terrain_rgb = Image.fromarray(shared_state.terrain_color, "RGB").convert("RGBA")
        canvas.paste(terrain_rgb, (0, banner_h))

        # ---- Water overlay -----------------------------------------
        if shared_state.water_mask.any():
            water_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            water_arr = np.zeros((h, w, 4), dtype=np.uint8)
            water_arr[shared_state.water_mask] = (60, 130, 200, 120)
            water_layer = Image.fromarray(water_arr, "RGBA")
            canvas.alpha_composite(water_layer, dest=(0, banner_h))

        # ---- Roads -------------------------------------------------
        road_layer = Image.new("RGBA", (w, total_h), (0, 0, 0, 0))
        road_draw = ImageDraw.Draw(road_layer)

        for path in shared_state.paths:
            if path.path_type == "road" and len(path.waypoints) > 1:
                # Offset waypoints by banner
                pts = [(px, py + banner_h) for (px, py) in path.waypoints]
                # Dark border (wider)
                road_draw.line(pts, fill=(90, 70, 40, 255), width=5, joint="curve")
                # Light center fill
                road_draw.line(pts, fill=(175, 155, 115, 255), width=3, joint="curve")
            elif path.path_type == "trail" and len(path.waypoints) > 1:
                pts = [(px, py + banner_h) for (px, py) in path.waypoints]
                # Thin dashed trail style -- draw every other segment
                for i in range(0, len(pts) - 1, 2):
                    seg_end = min(i + 1, len(pts) - 1)
                    road_draw.line([pts[i], pts[seg_end]], fill=(140, 120, 85, 200), width=2)
            elif path.path_type in ("river", "corridor") and len(path.waypoints) > 1:
                pts = [(px, py + banner_h) for (px, py) in path.waypoints]
                road_draw.line(pts, fill=(50, 110, 170, 180), width=max(3, path.width), joint="curve")

        canvas.alpha_composite(road_layer)

        # ---- Buildings / structures --------------------------------
        struct_layer = Image.new("RGBA", (w, total_h), (0, 0, 0, 0))
        struct_draw = ImageDraw.Draw(struct_layer)

        for entity in shared_state.entities:
            if entity.entity_type in ("building", "room", "structure"):
                x, y = entity.position
                y += banner_h
                bw, bh = entity.size

                # Pick fill color
                meta_color = entity.metadata.get("color", None)
                if meta_color and isinstance(meta_color, (list, tuple)) and len(meta_color) >= 3:
                    fill_r, fill_g, fill_b = int(meta_color[0]), int(meta_color[1]), int(meta_color[2])
                elif entity.entity_type == "room":
                    fill_r, fill_g, fill_b = 140, 138, 130
                else:
                    fill_r, fill_g, fill_b = 160, 120, 75

                # Shadow (offset 2px down-right, 50% opacity black)
                struct_draw.rectangle(
                    [x + 2, y + 2, x + bw + 1, y + bh + 1],
                    fill=(0, 0, 0, 128),
                )
                # Walls (2px border in darker tone)
                wall = (max(fill_r - 60, 0), max(fill_g - 60, 0), max(fill_b - 60, 0), 240)
                struct_draw.rectangle([x, y, x + bw - 1, y + bh - 1], fill=wall)
                # Floor interior (inset 2px)
                if bw > 6 and bh > 6:
                    floor = (fill_r, fill_g, fill_b, 230)
                    struct_draw.rectangle(
                        [x + 2, y + 2, x + bw - 3, y + bh - 3], fill=floor)
                # Roof ridge line (darker stripe across top third)
                if bh > 10 and entity.entity_type != "room":
                    ridge_y = y + bh // 3
                    roof_c = (max(fill_r - 35, 0), max(fill_g - 35, 0), max(fill_b - 35, 0), 200)
                    struct_draw.line([(x + 2, ridge_y), (x + bw - 3, ridge_y)],
                                     fill=roof_c, width=1)
                # Door (small dark square on bottom edge, centered)
                if bw > 8 and bh > 8:
                    door_w = max(2, bw // 6)
                    door_h = max(3, bh // 5)
                    dx = x + (bw - door_w) // 2
                    dy = y + bh - door_h - 1
                    struct_draw.rectangle([dx, dy, dx + door_w, dy + door_h],
                                          fill=(50, 35, 20, 255))
                # Window dots (small light squares on walls)
                if bw > 14 and bh > 14 and entity.entity_type != "room":
                    win_c = (200, 210, 180, 200)
                    # Left window
                    wx = x + bw // 4
                    wy = y + bh // 3
                    struct_draw.rectangle([wx, wy, wx + 2, wy + 2], fill=win_c)
                    # Right window
                    wx2 = x + 3 * bw // 4 - 2
                    struct_draw.rectangle([wx2, wy, wx2 + 2, wy + 2], fill=win_c)
                # Outline
                outline_c = (max(fill_r - 70, 0), max(fill_g - 70, 0), max(fill_b - 70, 0), 255)
                struct_draw.rectangle(
                    [x, y, x + bw - 1, y + bh - 1],
                    outline=outline_c, width=1,
                )

        canvas.alpha_composite(struct_layer)

        # ---- Labels ------------------------------------------------
        if show_labels:
            font_large = _load_font(max(12, w // 35), bold=True)
            font_medium = _load_font(max(9, w // 50))
            font_small = _load_font(max(7, w // 65))

            label_layer = Image.new("RGBA", (w, total_h), (0, 0, 0, 0))
            label_draw = ImageDraw.Draw(label_layer)

            for label in shared_state.labels:
                if label.category == "title":
                    continue  # drawn in banner instead
                elif label.category == "water_feature":
                    font = font_medium
                    lx, ly = label.position
                    ly += banner_h
                    # Subtle shadow behind water text
                    label_draw.text((lx + 1, ly + 1), label.text,
                                    fill=(0, 0, 0, 80), font=font, anchor="mm")
                    label_draw.text((lx, ly), label.text,
                                    fill=label.color, font=font, anchor="mm")
                else:
                    font = font_small
                    lx, ly = label.position
                    ly += banner_h - 8  # above the building
                    # Halo for readability
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            if dx or dy:
                                label_draw.text((lx + dx, ly + dy), label.text,
                                                fill=(255, 255, 255, 160), font=font, anchor="lb")
                    label_draw.text((lx, ly), label.text,
                                    fill=label.color, font=font, anchor="lb")

            canvas.alpha_composite(label_layer)

        # ---- Grid --------------------------------------------------
        if show_grid:
            grid_layer = Image.new("RGBA", (w, total_h), (0, 0, 0, 0))
            grid_draw = ImageDraw.Draw(grid_layer)
            grid_spacing = max(32, w // 16)
            for gx in range(0, w, grid_spacing):
                grid_draw.line([(gx, banner_h), (gx, total_h)], fill=(0, 0, 0, 40), width=1)
            for gy in range(banner_h, total_h, grid_spacing):
                grid_draw.line([(0, gy), (w, gy)], fill=(0, 0, 0, 40), width=1)
            canvas.alpha_composite(grid_layer)

        # ---- Vignette / atmosphere ---------------------------------
        vig = self._make_vignette(w, total_h, banner_h)
        canvas.alpha_composite(vig)

        # ---- Title banner ------------------------------------------
        if title_label is not None and banner_h > 0:
            ban = Image.new("RGBA", (w, banner_h), (35, 25, 15, 245))
            ban_draw = ImageDraw.Draw(ban)

            # Decorative thin lines
            ban_draw.line([(8, banner_h - 2), (w - 8, banner_h - 2)],
                          fill=(180, 150, 100, 200), width=1)
            ban_draw.line([(8, 1), (w - 8, 1)],
                          fill=(180, 150, 100, 200), width=1)

            # Centered title text -- shadow then main
            tx = w // 2
            ty = banner_h // 2
            ban_draw.text((tx + 1, ty + 1), title_label.text,
                          fill=(0, 0, 0, 180), font=font_title, anchor="mm")
            ban_draw.text((tx, ty), title_label.text,
                          fill=(235, 220, 190, 255), font=font_title, anchor="mm")

            canvas.alpha_composite(ban, dest=(0, 0))

        # ---- Legend ------------------------------------------------
        if show_legend:
            legend_font = _load_font(max(8, w // 70))
            self._draw_legend(canvas, shared_state, w, total_h, banner_h, legend_font)

        # ---- Compass rose ------------------------------------------
        self._draw_compass(canvas, w, total_h, banner_h)

        # ---- Border ------------------------------------------------
        border_layer = Image.new("RGBA", (w, total_h), (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(border_layer)
        border_draw.rectangle([0, 0, w - 1, total_h - 1], outline=(30, 20, 10, 255), width=2)
        # Thin gold inner border
        border_draw.rectangle([2, 2, w - 3, total_h - 3], outline=(160, 130, 80, 120), width=1)
        canvas.alpha_composite(border_layer)

        # ---- Save as RGB ------------------------------------------
        final = canvas.convert("RGB")
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        final.save(output_path, quality=95)

        # ---- Export per-layer data for pygame viewer ---------------
        output_dir = os.path.dirname(output_path) or "."
        map_data_json = self._export_layered_data(shared_state, output_dir)

        return {
            "output_path": output_path,
            "format": output_format,
            "dimensions": f"{w}x{total_h}",
            "file_size_kb": os.path.getsize(output_path) // 1024,
            "map_data_json": map_data_json,
        }

    # ------------------------------------------------------------------
    # Per-layer export for pygame viewer
    # ------------------------------------------------------------------
    @staticmethod
    def _convert_value(v):
        """Convert numpy/non-standard types to JSON-safe Python natives."""
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return float(v)
        if isinstance(v, np.ndarray):
            return v.tolist()
        if isinstance(v, dict):
            return {k: RendererAgent._convert_value(val) for k, val in v.items()}
        if isinstance(v, (list, tuple)):
            return [RendererAgent._convert_value(item) for item in v]
        return v

    def _export_layered_data(self, shared_state: SharedState, output_dir: str) -> str:
        """Export all z-level data as per-layer PNGs + a map_data.json manifest."""
        os.makedirs(output_dir, exist_ok=True)

        cfg = shared_state.config
        z_levels_data = []

        for z in sorted(shared_state.levels.keys()):
            level = shared_state.levels[z]

            # --- PNG filename ---
            if z >= 0:
                png_name = f"z_{z}.png"
            else:
                png_name = f"z_neg{abs(z)}.png"

            # --- Save terrain PNG ---
            if level.terrain_color is not None:
                img = Image.fromarray(level.terrain_color, "RGB")
                img.save(os.path.join(output_dir, png_name))

            # --- Walkability as flat 0/1 list ---
            if level.walkability is not None:
                walk_flat = level.walkability.astype(int).ravel().tolist()
            else:
                walk_flat = []

            # --- Entities ---
            entities_data = []
            for e in level.entities:
                entities_data.append({
                    "type": e.entity_type,
                    "x": int(e.position[0]),
                    "y": int(e.position[1]),
                    "w": int(e.size[0]),
                    "h": int(e.size[1]),
                    "variant": e.variant,
                    "metadata": self._convert_value(e.metadata),
                })

            z_levels_data.append({
                "z": z,
                "terrain_png": png_name,
                "walkability": walk_flat,
                "entities": entities_data,
            })

        # --- Transitions ---
        transitions_data = []
        for t in shared_state.transitions:
            transitions_data.append({
                "x": int(t.x),
                "y": int(t.y),
                "from_z": int(t.from_z),
                "to_z": int(t.to_z),
                "type": t.transition_type,
            })

        # --- Spawns ---
        spawns_data = []
        for sp in shared_state.spawns:
            spawns_data.append({
                "x": int(sp.x),
                "y": int(sp.y),
                "z": int(sp.z),
                "token_type": sp.token_type,
                "name": sp.name,
                "stats": self._convert_value(sp.stats),
                "ai_behavior": sp.ai_behavior,
            })

        # --- Labels across all levels ---
        labels_data = []
        for z in sorted(shared_state.levels.keys()):
            level = shared_state.levels[z]
            for lbl in level.labels:
                labels_data.append({
                    "x": int(lbl.position[0]),
                    "y": int(lbl.position[1]),
                    "z": z,
                    "text": lbl.text,
                    "category": lbl.category,
                })

        map_data = {
            "config": {
                "width": cfg.width,
                "height": cfg.height,
                "biome": cfg.biome,
                "map_type": cfg.map_type,
                "seed": cfg.seed,
            },
            "z_levels": z_levels_data,
            "transitions": transitions_data,
            "spawns": spawns_data,
            "labels": labels_data,
        }

        json_path = os.path.join(output_dir, "map_data.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(map_data, f, indent=2)

        return json_path

    # ------------------------------------------------------------------
    # Vignette
    # ------------------------------------------------------------------
    @staticmethod
    def _make_vignette(w: int, h: int, y_offset: int) -> Image.Image:
        """Create a dark vignette overlay that fades from edges inward."""
        vig = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        vig_arr = np.zeros((h, w, 4), dtype=np.uint8)

        # Build radial distance from center (normalised 0..1)
        cy, cx = (h - y_offset) / 2 + y_offset, w / 2
        yy, xx = np.mgrid[0:h, 0:w]
        # Elliptical distance so it works on non-square maps
        dx = (xx - cx) / (w / 2)
        dy = (yy - cy) / ((h - y_offset) / 2) if (h - y_offset) > 0 else (yy - cy)
        dist = np.sqrt(dx * dx + dy * dy)

        # Vignette strength ramps up outside radius ~0.7
        strength = np.clip((dist - 0.65) / 0.55, 0.0, 1.0)
        alpha = (strength * 90).astype(np.uint8)  # max alpha 90 for subtlety

        vig_arr[:, :, 3] = alpha
        return Image.fromarray(vig_arr, "RGBA")

    # ------------------------------------------------------------------
    # Compass rose
    # ------------------------------------------------------------------
    @staticmethod
    def _draw_compass(canvas: Image.Image, w: int, h: int, banner_h: int):
        """Draw a decorative compass rose in the top-right of the map area."""
        comp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(comp)

        cx = w - 50
        cy = banner_h + 50
        r = 22

        dark = (80, 60, 40, 255)
        red = (180, 40, 30, 255)
        light = (220, 200, 160, 200)

        # Outer ring
        draw.ellipse([cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4],
                      outline=dark, width=2)
        # Inner ring
        draw.ellipse([cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2],
                      outline=(160, 130, 80, 160), width=1)

        # Cardinal spokes -- N/S thicker
        draw.line([(cx, cy - r), (cx, cy + r)], fill=dark, width=2)
        draw.line([(cx - r, cy), (cx + r, cy)], fill=dark, width=2)

        # Ordinal spokes (thinner, shorter)
        diag = int(r * 0.6)
        for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
            draw.line([(cx, cy), (cx + dx * diag, cy + dy * diag)],
                      fill=(120, 100, 70, 180), width=1)

        # North arrow (red filled triangle)
        draw.polygon(
            [(cx, cy - r - 8), (cx - 5, cy - r + 4), (cx + 5, cy - r + 4)],
            fill=red)
        # South small triangle (dark)
        draw.polygon(
            [(cx, cy + r + 6), (cx - 4, cy + r - 2), (cx + 4, cy + r - 2)],
            fill=dark)

        # Center dot
        draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=light, outline=dark)

        # Letters
        font_c = _load_font(10, bold=True)
        draw.text((cx, cy - r - 11), "N", fill=red, font=font_c, anchor="mb")
        draw.text((cx, cy + r + 9), "S", fill=dark, font=font_c, anchor="mt")
        draw.text((cx - r - 7, cy), "W", fill=dark, font=font_c, anchor="rm")
        draw.text((cx + r + 7, cy), "E", fill=dark, font=font_c, anchor="lm")

        canvas.alpha_composite(comp)

    # ------------------------------------------------------------------
    # Legend
    # ------------------------------------------------------------------
    @staticmethod
    def _draw_legend(canvas: Image.Image, state, w: int, h: int,
                     banner_h: int, font: ImageFont.FreeTypeFont | ImageFont.ImageFont):
        """Draw a polished legend panel in the bottom-right corner."""
        legend_items: list[tuple[str, tuple[int, ...]]] = []
        entity_types = set(e.entity_type for e in state.entities)
        if "building" in entity_types or "structure" in entity_types:
            legend_items.append(("Buildings", (160, 120, 75)))
        if "room" in entity_types:
            legend_items.append(("Rooms", (140, 138, 130)))
        if state.water_mask.any():
            legend_items.append(("Water", (60, 130, 200)))
        has_roads = any(p.path_type == "road" for p in state.paths)
        if has_roads:
            legend_items.append(("Roads", (175, 155, 115)))
        has_trails = any(p.path_type == "trail" for p in state.paths)
        if has_trails:
            legend_items.append(("Trails", (140, 120, 85)))
        if "tree" in entity_types or "pine" in entity_types:
            legend_items.append(("Vegetation", (50, 120, 50)))

        if not legend_items:
            return

        item_h = 16
        pad = 8
        swatch = 12
        text_offset = swatch + 6

        # Measure widest text
        tmp = Image.new("RGBA", (1, 1))
        tmp_d = ImageDraw.Draw(tmp)
        max_tw = 0
        for name, _ in legend_items:
            bb = tmp_d.textbbox((0, 0), name, font=font)
            max_tw = max(max_tw, bb[2] - bb[0])

        panel_w = text_offset + max_tw + pad * 2
        panel_h = len(legend_items) * item_h + pad * 2

        lx = w - panel_w - 10
        ly = h - panel_h - 10

        leg = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ld = ImageDraw.Draw(leg)

        # Drop shadow
        ld.rounded_rectangle([lx + 2, ly + 2, lx + panel_w + 2, ly + panel_h + 2],
                              radius=4, fill=(0, 0, 0, 80))
        # Panel background
        ld.rounded_rectangle([lx, ly, lx + panel_w, ly + panel_h],
                              radius=4, fill=(255, 248, 235, 230),
                              outline=(80, 60, 40, 200), width=1)

        for i, (name, color) in enumerate(legend_items):
            iy = ly + pad + i * item_h
            ix = lx + pad
            # Color swatch with mini outline
            ld.rectangle([ix, iy, ix + swatch, iy + swatch],
                          fill=(*color, 255), outline=(40, 30, 20, 200))
            ld.text((ix + text_offset, iy + 1), name,
                     fill=(40, 30, 20, 255), font=font)

        canvas.alpha_composite(leg)

"""
RendererAgent — Composites all layers into final PNG or SVG output.
Draws terrain, water, roads, structures, assets, and labels.
"""

import numpy as np
from base_agent import BaseAgent
from shared_state import SharedState
from typing import Any
from PIL import Image, ImageDraw, ImageFont
import os


class RendererAgent(BaseAgent):
    name = "RendererAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        output_format = params.get("format", "png")
        output_path = params.get("output_path", "/sessions/brave-busy-fermat/mnt/outputs/generated_map.png")
        show_labels = params.get("show_labels", True)
        show_grid = params.get("show_grid", False)
        show_legend = params.get("show_legend", True)

        h, w = shared_state.config.height, shared_state.config.width

        # Create image from terrain color layer
        img = Image.fromarray(shared_state.terrain_color, 'RGB')
        draw = ImageDraw.Draw(img)

        # Draw path indicators (road markings)
        for path in shared_state.paths:
            if path.path_type == "road" and len(path.waypoints) > 1:
                # Draw subtle dashed center line
                for i in range(0, len(path.waypoints) - 1, 4):
                    p1 = path.waypoints[i]
                    p2_idx = min(i + 2, len(path.waypoints) - 1)
                    p2 = path.waypoints[p2_idx]
                    draw.line([p1, p2], fill=(160, 140, 105), width=1)

        # Draw structure outlines for emphasis
        for entity in shared_state.entities:
            if entity.entity_type in ("building", "room"):
                x, y = entity.position
                bw, bh = entity.size
                draw.rectangle(
                    [x, y, x + bw - 1, y + bh - 1],
                    outline=(40, 30, 20), width=1
                )

        # Draw labels
        if show_labels:
            try:
                # Try to load a font, fall back to default
                font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                                                max(12, w // 35))
                font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                                                 max(9, w // 50))
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                                                max(7, w // 65))
            except (IOError, OSError):
                font_large = ImageFont.load_default()
                font_medium = font_large
                font_small = font_large

            for label in shared_state.labels:
                if label.category == "title":
                    font = font_large
                    # Draw title with background
                    bbox = draw.textbbox(label.position, label.text, font=font)
                    pad = 4
                    draw.rectangle(
                        [bbox[0]-pad, bbox[1]-pad, bbox[2]+pad, bbox[3]+pad],
                        fill=(255, 248, 235, 200)
                    )
                    draw.text(label.position, label.text, fill=label.color,
                              font=font, anchor="mt")
                elif label.category == "water_feature":
                    font = font_medium
                    # Italicized water labels
                    draw.text(label.position, label.text, fill=label.color,
                              font=font, anchor="mm")
                else:
                    font = font_small
                    # Building labels with slight offset
                    lx, ly = label.position
                    ly -= 8  # above the building
                    draw.text((lx, ly), label.text, fill=label.color,
                              font=font, anchor="lb")

        # Optional grid overlay
        if show_grid:
            grid_spacing = max(32, w // 16)
            grid_color = (0, 0, 0, 40)
            for x in range(0, w, grid_spacing):
                draw.line([(x, 0), (x, h)], fill=(0, 0, 0), width=1)
            for y in range(0, h, grid_spacing):
                draw.line([(0, y), (w, y)], fill=(0, 0, 0), width=1)

        # Legend
        if show_legend:
            self._draw_legend(draw, shared_state, w, h, font_small if show_labels else None)

        # Compass rose
        self._draw_compass(draw, w, h)

        # Border
        draw.rectangle([0, 0, w-1, h-1], outline=(30, 20, 10), width=2)

        # Save
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, quality=95)

        return {
            "output_path": output_path,
            "format": output_format,
            "dimensions": f"{w}x{h}",
            "file_size_kb": os.path.getsize(output_path) // 1024,
        }

    def _draw_compass(self, draw: ImageDraw.Draw, w: int, h: int):
        """Draw a simple compass rose in the top-right corner."""
        cx, cy = w - 35, 35
        r = 15

        # N/S line
        draw.line([(cx, cy - r), (cx, cy + r)], fill=(80, 60, 40), width=2)
        # E/W line
        draw.line([(cx - r, cy), (cx + r, cy)], fill=(80, 60, 40), width=2)
        # N arrow
        draw.polygon([(cx, cy - r - 5), (cx - 4, cy - r + 3), (cx + 4, cy - r + 3)],
                      fill=(180, 40, 30))

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 8)
        except (IOError, OSError):
            font = ImageFont.load_default()

        draw.text((cx, cy - r - 8), "N", fill=(80, 40, 20), font=font, anchor="mb")

    def _draw_legend(self, draw, state, w, h, font):
        """Draw a small legend in the bottom-right corner."""
        if font is None:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 8)
            except (IOError, OSError):
                font = ImageFont.load_default()

        legend_items = []
        entity_types = set(e.entity_type for e in state.entities)
        if "building" in entity_types:
            legend_items.append(("Buildings", (120, 90, 60)))
        if state.water_mask.any():
            legend_items.append(("Water", (60, 130, 180)))
        has_roads = any(p.path_type == "road" for p in state.paths)
        if has_roads:
            legend_items.append(("Roads", (140, 115, 80)))
        if "tree" in entity_types or "pine" in entity_types:
            legend_items.append(("Vegetation", (30, 90, 30)))

        if not legend_items:
            return

        lx = w - 90
        ly = h - 15 - len(legend_items) * 14
        # Background
        draw.rectangle([lx - 5, ly - 5, w - 5, h - 5],
                        fill=(255, 248, 235), outline=(80, 60, 40))

        for i, (name, color) in enumerate(legend_items):
            y = ly + i * 14
            draw.rectangle([lx, y, lx + 10, y + 10], fill=color, outline=(40, 30, 20))
            draw.text((lx + 14, y + 1), name, fill=(40, 30, 20), font=font)

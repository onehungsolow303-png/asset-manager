"""Style Bible — JSON-backed art direction reference.

Every new generator (LoRA SD, Tripo3D, Nano Banana, Blender renderer)
reads the style bible BEFORE producing an asset, so the entire pipeline
shares one source of truth for art direction. This is what prevents the
"Frankenstein game" look where every generator picks its own palette and
the assets clash on screen.

The style bible has three layers:

  1. Global rules — apply to every asset
       art_style, perspective, color_palette, line_weight, shading_style
  2. Category overrides — per-category tweaks (characters get different
       lighting than tiles, UI gets different palette than environments)
  3. Director preferences — accumulating feedback from human review
       (approved references, rejected approaches, standing instructions)

Disk storage: a single JSON file at `.shared/state/style_bible.json`,
identical pattern to the existing `asset_catalog.json`. Loaded on
construction, modified via setter methods, persisted on every change.

Concrete fields (mirrors §5 of Development_Tool_Master_Prompt.docx):

    {
      "schema_version": "1.0.0",
      "art_style":     "D&D fantasy painterly, Forgotten Realms aesthetic",
      "perspective":   "top-down for tokens, three-quarter for portraits",
      "color_palette": {
        "primary":   ["#3a2818", "#5c3a1f", "#8b6332"],   # weathered browns
        "secondary": ["#1f3a5c", "#2d5180", "#4a7bb8"],   # deep blues for sky/water
        "accent":    ["#c4a460", "#e8c878", "#f5d98a"]    # warm gold highlights
      },
      "line_weight":   "1-2px crisp outlines, color slightly darker than fill",
      "shading_style": "painterly with soft gradients, 3-tone shading minimum",
      "lighting":      "warm key light from upper-left, cool fill from lower-right",
      "global_rules": [
        "no neon colors",
        "no modern weapons or technology",
        "weathered and grim tone, not bright cartoon",
        "all characters readable as silhouettes at 32x32"
      ],
      "category_overrides": {
        "creature_token":  {"perspective": "strict top-down circular framing"},
        "portrait":        {"perspective": "three-quarter bust, upper torso visible"},
        "item_icon":       {"perspective": "isometric 30deg, clean transparent bg"},
        "tileset":         {"perspective": "top-down, seamless edges"}
      },
      "director_preferences": {
        "approved_references": [],
        "rejected_approaches": [],
        "standing_instructions": []
      }
    }

The defaults below reflect the user's stated preference for D&D-style
fantasy art (per the conversation around the 33GB Roll20 library and
the Tripo3D dwarf reference). They are NOT prescriptive — the user can
edit the JSON file directly or call the setter methods at any time.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_STYLE_BIBLE_PATH = Path("C:/Dev/.shared/state/style_bible.json")


# Default art direction. Reflects the user's stated D&D fantasy preference
# from the asset pipeline conversation. Editable at runtime via setters or
# by hand-editing the JSON file.
_DEFAULT_BIBLE: dict[str, Any] = {
    "schema_version": "1.0.0",
    "art_style": (
        "D&D fantasy painterly, Forgotten Realms / Roll20 marketplace "
        "aesthetic. Detailed armor, realistic proportions, painterly "
        "textures. Avoid low-poly POLYGON / Synty style — too blocky."
    ),
    "perspective": (
        "top-down circular for combat tokens, three-quarter for portraits, "
        "isometric for items, top-down for tileset"
    ),
    "color_palette": {
        # Weathered earthy browns (camp, dungeon walls, leather armor)
        "primary": ["#3a2818", "#5c3a1f", "#8b6332", "#a07c4a"],
        # Deep blues + greys (sky, stone, steel)
        "secondary": ["#1f3a5c", "#2d5180", "#4a7bb8", "#6b6b75"],
        # Warm gold + crimson highlights (gold trim, blood, fire)
        "accent": ["#c4a460", "#e8c878", "#f5d98a", "#a8302a"],
    },
    "line_weight": (
        "1-2px crisp outlines, outline color slightly darker than the "
        "filled area it bounds (no pure black outlines)"
    ),
    "shading_style": (
        "painterly with soft gradients, minimum 3 shade levels per surface "
        "(shadow, midtone, highlight)"
    ),
    "lighting": (
        "warm key light from upper-left at ~45 degrees, cool fill from "
        "lower-right at ~15% intensity, soft rim light to separate "
        "subject from background"
    ),
    "global_rules": [
        "no neon or electric colors",
        "no modern weapons, vehicles, or technology",
        "weathered and grim tone — this is a post-Rot world, not a bright cartoon",
        "all creature tokens must be readable as silhouettes at 32x32",
        "all portraits must be recognizable at 128x128",
        "no copyrighted character likenesses (no D&D official IPs)",
    ],
    "category_overrides": {
        "creature_token": {
            "perspective": "strict top-down circular framing, character "
            "centered, no bleeding outside the disc",
            "size_default": "32x32 or 64x64",
            "background": "transparent",
        },
        "portrait": {
            "perspective": "three-quarter bust, upper torso visible, "
            "subject facing slightly off-camera",
            "size_default": "128x128 or 256x256",
            "background": "soft painterly fade or solid neutral",
        },
        "item_icon": {
            "perspective": "isometric 30 degrees, clean transparent bg",
            "size_default": "16x16, 32x32, or 64x64",
            "background": "transparent",
        },
        "tileset": {
            "perspective": "strict top-down with seamless tileable edges",
            "size_default": "32x32 per tile",
            "background": "opaque, color-matched to neighboring tiles",
        },
        "dungeon_tile": {
            "perspective": "top-down for floors, isometric or front-facing for walls",
            "size_default": "varies — match Forever engine grid",
            "background": "opaque",
        },
    },
    "director_preferences": {
        "approved_references": [],
        "rejected_approaches": [],
        "standing_instructions": [],
    },
}


class StyleBible:
    """Read/write accessor for the persisted style bible JSON."""

    def __init__(
        self,
        path: Path | None = None,
        persist: bool = True,
        seed_defaults: bool = True,
    ) -> None:
        self._path = path or DEFAULT_STYLE_BIBLE_PATH
        self._persist = persist
        self._data: dict[str, Any] = {}

        if self._persist and self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("[StyleBible] failed to load %s: %s", self._path, e)

        # Seed defaults if the on-disk bible is missing or empty. Tests
        # that want a clean slate can pass seed_defaults=False.
        if not self._data and seed_defaults:
            self._data = json.loads(json.dumps(_DEFAULT_BIBLE))  # deep copy
            self._save()

    # ── Read API ──────────────────────────────────────────────────

    def get_global(self, key: str, default: Any = None) -> Any:
        """Read a top-level field (art_style, perspective, palette, etc)."""
        return self._data.get(key, default)

    def get_category(self, category: str) -> dict[str, Any]:
        """Read the category override block for a kind, merged with
        global defaults so callers always get the EFFECTIVE rules.

        For each override field, the category value wins over the global.
        Fields not in the override fall through to global.
        """
        merged = {
            "art_style": self._data.get("art_style"),
            "perspective": self._data.get("perspective"),
            "color_palette": self._data.get("color_palette"),
            "line_weight": self._data.get("line_weight"),
            "shading_style": self._data.get("shading_style"),
            "lighting": self._data.get("lighting"),
            "global_rules": list(self._data.get("global_rules") or []),
        }
        override = (self._data.get("category_overrides") or {}).get(category, {})
        for k, v in override.items():
            merged[k] = v
        return merged

    def all(self) -> dict[str, Any]:
        """Return the full underlying dict (read-only contract — callers
        should not mutate the returned dict, but we don't deep-copy for
        performance)."""
        return self._data

    # ── Write API ─────────────────────────────────────────────────

    def set_global(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def add_global_rule(self, rule: str) -> None:
        rules = list(self._data.get("global_rules") or [])
        if rule not in rules:
            rules.append(rule)
            self._data["global_rules"] = rules
            self._save()

    def set_category_override(self, category: str, key: str, value: Any) -> None:
        overrides = dict(self._data.get("category_overrides") or {})
        cat = dict(overrides.get(category) or {})
        cat[key] = value
        overrides[category] = cat
        self._data["category_overrides"] = overrides
        self._save()

    def add_director_approval(self, reference_id: str) -> None:
        self._append_director_list("approved_references", reference_id)

    def add_director_rejection(self, approach: str) -> None:
        self._append_director_list("rejected_approaches", approach)

    def add_standing_instruction(self, instruction: str) -> None:
        self._append_director_list("standing_instructions", instruction)

    def _append_director_list(self, key: str, value: str) -> None:
        prefs = dict(self._data.get("director_preferences") or {})
        items = list(prefs.get(key) or [])
        if value not in items:
            items.append(value)
            prefs[key] = items
            self._data["director_preferences"] = prefs
            self._save()

    # ── Prompt composition helpers ────────────────────────────────

    def render_prompt_preamble(self, category: str) -> str:
        """Build a text block that can be prepended to any AI generation
        prompt to enforce the style bible. The output reads like:

            "Style: D&D fantasy painterly, top-down circular framing.
             Palette: warm browns, deep blues, gold accents.
             Rules: no neon, weathered tone. Lighting: warm key from
             upper-left."

        Each generator can decide how much to include. Tripo3D doesn't
        need lighting language; Nano Banana benefits from the full block.
        """
        cat = self.get_category(category)
        parts: list[str] = []
        if cat.get("art_style"):
            parts.append(f"Style: {cat['art_style']}")
        if cat.get("perspective"):
            parts.append(f"Perspective: {cat['perspective']}")
        palette = cat.get("color_palette") or {}
        if palette:
            primary = ", ".join(palette.get("primary") or [])
            accent = ", ".join(palette.get("accent") or [])
            if primary or accent:
                parts.append(f"Palette: primary {primary}; accent {accent}")
        if cat.get("lighting"):
            parts.append(f"Lighting: {cat['lighting']}")
        rules = cat.get("global_rules") or []
        if rules:
            parts.append("Rules: " + "; ".join(rules))
        return ". ".join(parts) + "."

    # ── Persistence ───────────────────────────────────────────────

    def _save(self) -> None:
        if not self._persist:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning("[StyleBible] persist failed: %s", e)

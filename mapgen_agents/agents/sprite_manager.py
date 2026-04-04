"""
SpriteManager — Loads real image assets from the Assets/ directory and
composites them onto the rendered map.  Falls back gracefully to None
when the Assets directory is missing so callers can use colored shapes.

Dependencies: Pillow (PIL), os, pathlib — nothing else.
"""

import os
import hashlib
from pathlib import Path
from typing import Optional

from PIL import Image


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _resolve_assets_root() -> Optional[Path]:
    """
    Return the absolute path to the Assets/ directory that lives at the
    project root.  The project root is two levels up from this file:
        mapgen_agents/agents/sprite_manager.py  ->  ../../Assets
    Returns None if the directory does not exist.
    """
    project_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assets_dir = project_root / "Assets"
    if assets_dir.is_dir():
        return assets_dir
    return None


# ---------------------------------------------------------------------------
# SpriteManager
# ---------------------------------------------------------------------------

class SpriteManager:
    """
    Scans the Assets/ tree for building and NPC images, caches resized
    RGBA versions, and hands them out on request.
    """

    # Supported image extensions (case-insensitive check)
    _IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}

    def __init__(self, assets_root: Optional[Path] = None):
        self._assets_root = assets_root or _resolve_assets_root()
        # raw Path lists
        self._building_paths: list[Path] = []
        self._npc_paths: list[Path] = []
        # caches: (path, (w,h)) -> RGBA Image
        self._cache: dict[tuple[str, tuple[int, int]], Image.Image] = {}

        if self._assets_root is not None:
            self._scan()

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def _scan(self) -> None:
        """Walk the Assets directory and collect building / NPC image paths."""
        buildings_dir = self._assets_root / "Buildings"
        npcs_dir = self._assets_root / "NPCs"

        if buildings_dir.is_dir():
            self._building_paths = sorted(
                p for p in buildings_dir.iterdir()
                if p.suffix.lower() in self._IMAGE_EXTS
            )

        if npcs_dir.is_dir():
            self._npc_paths = sorted(
                p for p in npcs_dir.iterdir()
                if p.suffix.lower() in self._IMAGE_EXTS
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_rgba(self, path: Path, size: tuple[int, int]) -> Image.Image:
        """
        Load *path*, resize to *size* with high-quality downscaling,
        and ensure the result has an alpha channel.  Results are cached.
        """
        key = (str(path), size)
        if key in self._cache:
            return self._cache[key]

        img = Image.open(path)
        img = img.convert("RGBA")
        img = img.resize(size, Image.LANCZOS)
        self._cache[key] = img
        return img

    @staticmethod
    def _pick_index(paths: list[Path], variant: Optional[str],
                    position: Optional[tuple[int, int]] = None) -> int:
        """
        Choose a deterministic-but-varied index into *paths*.

        * If *variant* is given, it is hashed to select the sprite.
        * Otherwise *position* is hashed (gives spatial variety on the map).
        * If neither is provided, index 0 is returned.
        """
        if not paths:
            return 0
        if variant is not None:
            digest = int(hashlib.md5(variant.encode()).hexdigest(), 16)
            return digest % len(paths)
        if position is not None:
            digest = int(hashlib.md5(f"{position[0]},{position[1]}".encode()).hexdigest(), 16)
            return digest % len(paths)
        return 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """True when at least one sprite has been found."""
        return bool(self._building_paths or self._npc_paths)

    @property
    def building_count(self) -> int:
        return len(self._building_paths)

    @property
    def npc_count(self) -> int:
        return len(self._npc_paths)

    def get_building_sprite(
        self,
        variant: Optional[str] = None,
        size: tuple[int, int] = (32, 32),
        position: Optional[tuple[int, int]] = None,
    ) -> Optional[Image.Image]:
        """
        Return a building sprite as an RGBA PIL Image at the requested
        *size*, or None if no building assets are loaded.

        *variant* or *position* seed the random selection so each map
        entity gets a consistent but varied sprite.
        """
        if not self._building_paths:
            return None
        idx = self._pick_index(self._building_paths, variant, position)
        return self._load_rgba(self._building_paths[idx], size)

    def get_npc_sprite(
        self,
        variant: Optional[str] = None,
        size: tuple[int, int] = (16, 16),
        position: Optional[tuple[int, int]] = None,
    ) -> Optional[Image.Image]:
        """
        Return an NPC token as an RGBA PIL Image at the requested *size*,
        or None if no NPC assets are loaded.
        """
        if not self._npc_paths:
            return None
        idx = self._pick_index(self._npc_paths, variant, position)
        return self._load_rgba(self._npc_paths[idx], size)


# ---------------------------------------------------------------------------
# Compositing helper
# ---------------------------------------------------------------------------

# Entity types that map to building sprites
_BUILDING_TYPES = {"building", "room", "house", "shop", "temple", "church",
                   "tower", "fort", "castle", "inn", "tavern", "warehouse",
                   "barracks", "manor"}

# Entity types that map to NPC sprites
_NPC_TYPES = {"npc", "guard", "villager", "merchant", "dwarf", "character",
              "token", "creature"}


def composite_sprites(
    base_image: Image.Image,
    shared_state,
    sprite_manager: SpriteManager,
) -> Image.Image:
    """
    Paste sprites on top of the rendered base image.

    Parameters
    ----------
    base_image : PIL.Image.Image
        The fully rendered map (RGB or RGBA).
    shared_state : SharedState
        The generation state whose `.entities` list drives placement.
    sprite_manager : SpriteManager
        A loaded SpriteManager instance.

    Returns
    -------
    PIL.Image.Image
        The composited image (RGBA).
    """
    if not sprite_manager.available:
        return base_image

    # Ensure base is RGBA so alpha compositing works
    result = base_image.convert("RGBA")
    map_w, map_h = result.size

    for entity in shared_state.entities:
        etype = entity.entity_type.lower()
        x, y = entity.position
        ew, eh = entity.size

        sprite: Optional[Image.Image] = None

        if etype in _BUILDING_TYPES:
            # Size the sprite to the entity's footprint, clamped to
            # reasonable bounds so we don't paste a 1x1 or 2000x2000 image.
            sw = max(16, min(ew, 128))
            sh = max(16, min(eh, 128))
            sprite = sprite_manager.get_building_sprite(
                variant=entity.variant or None,
                size=(sw, sh),
                position=(x, y),
            )
        elif etype in _NPC_TYPES:
            sprite = sprite_manager.get_npc_sprite(
                variant=entity.variant or None,
                size=(16, 16),
                position=(x, y),
            )

        if sprite is None:
            continue

        # Centre the sprite over the entity position
        sw, sh = sprite.size
        paste_x = x + (ew - sw) // 2
        paste_y = y + (eh - sh) // 2

        # Clamp so we don't paste outside the image
        if paste_x < 0:
            paste_x = 0
        if paste_y < 0:
            paste_y = 0
        if paste_x + sw > map_w:
            paste_x = map_w - sw
        if paste_y + sh > map_h:
            paste_y = map_h - sh

        # Skip if still out of bounds (sprite bigger than map — shouldn't happen)
        if paste_x < 0 or paste_y < 0:
            continue

        # Paste with alpha mask for proper transparency
        result.paste(sprite, (paste_x, paste_y), mask=sprite)

    return result

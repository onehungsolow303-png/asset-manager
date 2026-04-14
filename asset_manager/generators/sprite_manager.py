"""
SpriteManager — Loads real image assets from the Assets/ directory and
composites them onto the rendered map.  Falls back gracefully to None
when the Assets directory is missing so callers can use colored shapes.

Supports auto-discovery of custom asset packs: every subdirectory under
Assets/ becomes a named pack.  Nested subdirectories are flattened with
underscores (e.g. ``Assets/Terrain/Grass/`` -> pack ``terrain_grass``).

Sprite sheets are also supported.  Drop a ``_sheet.json`` alongside a
sheet image and the manager will slice it into individual tiles
automatically.

Dependencies: Pillow (PIL), os, json, pathlib — nothing else.
"""

import hashlib
import json
import os
from pathlib import Path

from PIL import Image

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _resolve_assets_root() -> Path | None:
    """
    Return the absolute path to the Assets/ directory that lives at the
    project root.  The project root is two levels up from this file:
        mapgen_agents/agents/sprite_manager.py  ->  ../../Assets
    Returns None if the directory does not exist.
    """
    # sprite_manager.py lives at mapgen_agents/agents/  — project root is 2 dirs up
    here = Path(os.path.abspath(__file__)).parent  # mapgen_agents/agents
    project_root = here.parent.parent  # Map Generator/
    assets_dir = project_root / "Assets"
    if assets_dir.is_dir():
        return assets_dir
    return None


# ---------------------------------------------------------------------------
# SpriteManager
# ---------------------------------------------------------------------------


class SpriteManager:
    """
    Scans an assets directory tree for image files, organises them into
    named packs (one per subdirectory), caches resized RGBA versions,
    and hands them out on request.

    Backwards-compatible: ``get_building_sprite()`` and ``get_npc_sprite()``
    delegate to the ``"buildings"`` and ``"npcs"`` packs respectively.
    """

    # Supported image extensions (case-insensitive check)
    _IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, assets_root: Path | None = None):
        self._assets_root = assets_root or _resolve_assets_root()

        # pack_name -> sorted list of image Paths
        self._packs: dict[str, list[Path]] = {}

        # Legacy convenience aliases (kept in sync with _packs)
        self._building_paths: list[Path] = []
        self._npc_paths: list[Path] = []

        # (str(path), (w, h)) -> RGBA Image
        self._cache: dict[tuple[str, tuple[int, int]], Image.Image] = {}

        # pack_name -> list of PIL Images extracted from sprite sheets
        self._sheet_sprites: dict[str, list[Image.Image]] = {}

        if self._assets_root is not None:
            self._scan()

    @classmethod
    def from_directory(cls, directory: str) -> "SpriteManager":
        """
        Create a SpriteManager rooted at an arbitrary directory instead
        of the default ``Assets/`` location.

        Parameters
        ----------
        directory : str
            Absolute or relative path to the directory to scan.  Every
            immediate-or-nested subdirectory that contains images becomes
            a pack.

        Returns
        -------
        SpriteManager
        """
        path = Path(directory).resolve()
        if not path.is_dir():
            raise FileNotFoundError(f"Directory does not exist: {path}")
        return cls(assets_root=path)

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def _scan(self) -> None:
        """Walk the assets root and register every subdirectory as a pack."""
        self._packs.clear()
        self._sheet_sprites.clear()

        for dirpath, _dirnames, filenames in os.walk(self._assets_root):
            dirpath = Path(dirpath)

            # Skip the root directory itself — only subdirectories are packs
            if dirpath == self._assets_root:
                continue

            # Build the pack name from the relative path, joined with
            # underscores and lowercased.
            # e.g.  Assets/Terrain/Grass  ->  terrain_grass
            rel = dirpath.relative_to(self._assets_root)
            pack_name = "_".join(rel.parts).lower()

            # Collect image files in this directory (non-recursive per-dir)
            images = sorted(
                dirpath / f for f in filenames if Path(f).suffix.lower() in self._IMAGE_EXTS
            )

            if images:
                self._packs[pack_name] = images

            # Handle sprite sheet metadata
            sheet_meta = dirpath / "_sheet.json"
            if sheet_meta.is_file():
                self._load_sprite_sheet(pack_name, dirpath, sheet_meta)

        # Keep legacy aliases in sync
        self._building_paths = self._packs.get("buildings", [])
        self._npc_paths = self._packs.get("npcs", [])

    def _load_sprite_sheet(self, pack_name: str, directory: Path, meta_path: Path) -> None:
        """
        Parse a ``_sheet.json`` file and slice the accompanying sprite
        sheet image into individual tiles.

        Expected JSON format::

            {
                "tile_size": [32, 32],
                "columns": 4,
                "sprites": ["grass1", "grass2", "dirt1", "stone1"]
            }

        The sheet image must be the first image file (alphabetically) in
        the same directory that is *not* already registered as a regular
        pack sprite, OR the only image present.
        """
        try:
            with open(meta_path, encoding="utf-8") as fh:
                meta = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return

        tile_w, tile_h = meta.get("tile_size", [32, 32])
        columns: int = meta.get("columns", 1)
        sprite_names: list[str] = meta.get("sprites", [])

        if not sprite_names:
            return

        # Find the sheet image — pick the first image in the directory
        sheet_candidates = sorted(
            p for p in directory.iterdir() if p.suffix.lower() in self._IMAGE_EXTS
        )
        if not sheet_candidates:
            return

        sheet_path = sheet_candidates[0]
        try:
            sheet_img = Image.open(sheet_path).convert("RGBA")
        except OSError:
            return

        tiles: list[Image.Image] = []
        for idx in range(len(sprite_names)):
            col = idx % columns
            row = idx // columns
            x = col * tile_w
            y = row * tile_h
            # Guard against going past the image bounds
            if x + tile_w > sheet_img.width or y + tile_h > sheet_img.height:
                break
            tile = sheet_img.crop((x, y, x + tile_w, y + tile_h))
            tiles.append(tile)

        if tiles:
            self._sheet_sprites[pack_name] = tiles

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
    def _pick_index(
        paths_or_count, variant: str | None, position: tuple[int, int] | None = None
    ) -> int:
        """
        Choose a deterministic-but-varied index.

        *paths_or_count* may be a list (uses ``len()``) or an int.

        * If *variant* is given, it is hashed to select the sprite.
        * Otherwise *position* is hashed (gives spatial variety on the map).
        * If neither is provided, index 0 is returned.
        """
        count = paths_or_count if isinstance(paths_or_count, int) else len(paths_or_count)
        if count == 0:
            return 0
        if variant is not None:
            digest = int(hashlib.md5(variant.encode()).hexdigest(), 16)
            return digest % count
        if position is not None:
            digest = int(hashlib.md5(f"{position[0]},{position[1]}".encode()).hexdigest(), 16)
            return digest % count
        return 0

    # ------------------------------------------------------------------
    # Public API — pack discovery
    # ------------------------------------------------------------------

    def list_packs(self) -> dict[str, int]:
        """
        Return a mapping of pack names to their sprite counts.

        Sprite-sheet tiles are included in the count when present.
        """
        result: dict[str, int] = {}
        all_names = set(self._packs.keys()) | set(self._sheet_sprites.keys())
        for name in sorted(all_names):
            count = len(self._packs.get(name, []))
            count += len(self._sheet_sprites.get(name, []))
            result[name] = count
        return result

    # ------------------------------------------------------------------
    # Public API — generic sprite access
    # ------------------------------------------------------------------

    def get_sprite(
        self,
        pack: str,
        variant: str | None = None,
        size: tuple[int, int] = (32, 32),
        position: tuple[int, int] | None = None,
    ) -> Image.Image | None:
        """
        Return a sprite from the named *pack* as an RGBA PIL Image at
        the requested *size*, or ``None`` if the pack does not exist or
        is empty.

        Sprites from regular image files and sprite-sheet tiles are
        combined into a single logical pool before selection.

        Parameters
        ----------
        pack : str
            Pack name (lowercase, underscores for nested dirs).
        variant : str, optional
            Seed string for deterministic selection.
        size : tuple[int, int]
            Target (width, height) for the returned image.
        position : tuple[int, int], optional
            Map position used as selection seed when *variant* is None.
        """
        pack = pack.lower()
        file_sprites = self._packs.get(pack, [])
        sheet_tiles = self._sheet_sprites.get(pack, [])

        total = len(file_sprites) + len(sheet_tiles)
        if total == 0:
            return None

        idx = self._pick_index(total, variant, position)

        if idx < len(file_sprites):
            return self._load_rgba(file_sprites[idx], size)
        else:
            # It is a sheet tile — resize a copy to the requested size
            tile = sheet_tiles[idx - len(file_sprites)].copy()
            if tile.size != size:
                tile = tile.resize(size, Image.LANCZOS)
            return tile

    # ------------------------------------------------------------------
    # Public API — legacy convenience methods
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """True when at least one sprite has been found."""
        return bool(self._packs or self._sheet_sprites)

    @property
    def building_count(self) -> int:
        return len(self._building_paths)

    @property
    def npc_count(self) -> int:
        return len(self._npc_paths)

    def get_building_sprite(
        self,
        variant: str | None = None,
        size: tuple[int, int] = (32, 32),
        position: tuple[int, int] | None = None,
    ) -> Image.Image | None:
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
        variant: str | None = None,
        size: tuple[int, int] = (16, 16),
        position: tuple[int, int] | None = None,
    ) -> Image.Image | None:
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
_BUILDING_TYPES = {
    "building",
    "room",
    "house",
    "shop",
    "temple",
    "church",
    "tower",
    "fort",
    "castle",
    "inn",
    "tavern",
    "warehouse",
    "barracks",
    "manor",
}

# Entity types that map to NPC sprites
_NPC_TYPES = {"npc", "guard", "villager", "merchant", "dwarf", "character", "token", "creature"}


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

        sprite: Image.Image | None = None

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

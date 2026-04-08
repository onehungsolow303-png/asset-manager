"""Seed the asset library with a default set of creature tokens.

Idempotent: skips any token whose PNG already exists on disk. Runs once
at Asset Manager startup so the library is non-empty out of the box and
Forever engine's BattleManager.RequestEnemySprites gets visible hits
without the user having to bake anything manually.

Each seeded token is a procedural sprite from
`asset_manager.generators.procedural_sprite.generate_creature_token`
with a distinctive base color, written to
`<baked_root>/creature_token/<enemy_lower>.png` and registered in the
catalog with kind=creature_token, the matching biome, and a single tag
matching the enemy's lowercased name. This is the same shape Forever
engine's BattleManager queries for in `RequestEnemySprites`.

To regenerate after editing the seed list:
  1. Stop Asset Manager
  2. Delete the affected PNGs under .shared/baked/creature_token/
  3. Restart Asset Manager (seed will rebuild missing entries)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from asset_manager.generators.procedural_sprite import (
    generate_creature_token,
    generate_item_icon,
)
from asset_manager.library.catalog import DEFAULT_BAKED_ROOT
from asset_manager.library.manifest import make_manifest

logger = logging.getLogger(__name__)

# (enemy_name, biome, base_color rgba) — keyed off Forever engine's
# EncounterData.GenerateRandom enemy definitions. Colors are intentionally
# distinctive so the procedural circles read as different creatures even
# at 32x32. Tags will be {name.lower()}.
_SEED_CREATURES: list[tuple[str, str, tuple[int, int, int, int]]] = [
    # Forest
    ("Wolf",            "forest",  (140, 140, 145, 255)),  # slate gray
    ("Wolf Pup",        "forest",  (160, 160, 170, 255)),  # lighter gray
    ("Dire Wolf",       "forest",  (90,  90,  100, 255)),  # darker, larger feel
    ("Alpha Wolf",      "forest",  (60,  60,  80,  255)),  # near-black, intimidating
    # Plains
    ("Bandit",          "plains",  (130, 90,  60,  255)),  # leather brown
    ("Bandit Captain",  "plains",  (90,  50,  30,  255)),  # darker leather + steel
    ("Cultist",         "plains",  (60,  20,  60,  255)),  # purple robe
    # Ruins
    ("Skeleton",        "ruins",   (230, 225, 205, 255)),  # bone
    ("Skeleton Archer", "ruins",   (210, 200, 170, 255)),  # weathered bone
    ("Mutant",          "ruins",   (90,  140, 70,  255)),  # bile green
    ("Mutant Hulk",     "ruins",   (60,  100, 40,  255)),  # darker, mass
    # Dungeon (static encounter "dungeon_boss")
    ("Hollow Guardian", "dungeon", (170, 130, 60,  255)),  # tarnished bronze
    # Castle (static encounter "castle_boss")
    ("The Rot King",    "castle",  (120, 30,  40,  255)),  # rust red
    ("Rot Knight",      "castle",  (110, 80,  40,  255)),  # dark rust
    ("Plague Rat",      "castle",  (80,  50,  30,  255)),  # dark vermin
    # Generic fallback
    ("Rat",             "default", (120, 90,  60,  255)),  # default vermin
]

_TOKEN_KIND = "creature_token"
_TOKEN_SIZE = 32


def seed_default_creature_tokens(
    catalog: Any,
    baked_root: Path | None = None,
) -> int:
    """Generate the default creature tokens and register them in catalog.

    Returns the number of tokens newly generated. Existing PNGs are
    detected by path and not regenerated. Existing catalog entries with
    the same asset_id are not overwritten by add() either.
    """
    root = baked_root or DEFAULT_BAKED_ROOT
    out_dir = root / _TOKEN_KIND
    out_dir.mkdir(parents=True, exist_ok=True)

    generated = 0
    for name, biome, color in _SEED_CREATURES:
        asset_id = name.lower().replace(" ", "_")
        png_path = out_dir / f"{asset_id}.png"

        if png_path.exists():
            # File on disk is the source of truth; ensure catalog has it.
            # The catalog auto-scan picked it up at construction, but the
            # auto-scan doesn't know the biome/tags — only the path. Add
            # a fuller manifest here so /select can match by biome/tags.
            _ensure_manifest(catalog, asset_id, name, biome, png_path)
            continue

        try:
            generate_creature_token(color, size=_TOKEN_SIZE, out_path=png_path)
        except Exception as e:
            logger.warning("[seed] failed to generate %s: %s", name, e)
            continue

        _ensure_manifest(catalog, asset_id, name, biome, png_path)
        generated += 1

    if generated > 0:
        logger.info("[seed] created %d default creature tokens under %s", generated, out_dir)
    return generated


def _ensure_manifest(
    catalog: Any,
    asset_id: str,
    name: str,
    biome: str,
    png_path: Path,
) -> None:
    """Add or update the manifest entry so it carries biome + tags.

    The catalog's auto-scan picks up bare PNGs and stores only
    {asset_id, kind, path}. The selector needs biome + tags to score
    matches accurately, so we always overwrite the entry here with a
    richer manifest. Idempotent — calling twice is a no-op semantically.
    """
    manifest = make_manifest(
        asset_id=asset_id,
        kind=_TOKEN_KIND,
        path=str(png_path),
        biome=biome,
        tags=[name.lower()],
        source="procedural",
        license="CC0",
        cost_usd=0.0,
        swap_safe=True,
    )
    catalog.add(asset_id, manifest)


# ─── Item icon seeds ─────────────────────────────────────────────────────
#
# Forever engine's PlayerData.cs declares three item IDs:
#   100  Food
#   101  Water
#   102  HealthPotion
#
# Until cloud art lands, the procedural item icons give the dialogue UI,
# inventory screen, and combat HUD a real visual placeholder per item
# kind instead of a single generic square. The asset_id is keyed by the
# C# constant name in lowercase (food / water / health_potion) so
# /select?kind=item_icon&tags=[health_potion] hits cleanly.
#
# Each entry: (name, color rgba, shape) — shape is one of square/circle/diamond
# from generators.procedural_sprite.generate_item_icon.

_SEED_ITEMS: list[tuple[str, tuple[int, int, int, int], str]] = [
    ("Food",          (180, 120, 60,  255), "square"),   # warm bread brown
    ("Water",         (60,  140, 220, 255), "circle"),   # deep blue droplet
    ("Health Potion", (220, 50,  60,  255), "diamond"),  # crimson flask
]

_ITEM_KIND = "item_icon"
_ITEM_SIZE = 16


def seed_default_item_icons(
    catalog: Any,
    baked_root: Path | None = None,
) -> int:
    """Generate the default item icons and register them in the catalog.

    Mirrors `seed_default_creature_tokens`: idempotent, file-on-disk is
    the source of truth, existing PNGs are not regenerated, and a
    full manifest with tags is registered so /select can match by tag.

    Returns the number of icons newly generated.
    """
    root = baked_root or DEFAULT_BAKED_ROOT
    out_dir = root / _ITEM_KIND
    out_dir.mkdir(parents=True, exist_ok=True)

    generated = 0
    for name, color, shape in _SEED_ITEMS:
        asset_id = name.lower().replace(" ", "_")
        png_path = out_dir / f"{asset_id}.png"

        if png_path.exists():
            _ensure_item_manifest(catalog, asset_id, name, shape, png_path)
            continue

        try:
            generate_item_icon(color, shape=shape, size=_ITEM_SIZE, out_path=png_path)
        except Exception as e:
            logger.warning("[seed] failed to generate item icon %s: %s", name, e)
            continue

        _ensure_item_manifest(catalog, asset_id, name, shape, png_path)
        generated += 1

    if generated > 0:
        logger.info("[seed] created %d default item icons under %s", generated, out_dir)
    return generated


def _ensure_item_manifest(
    catalog: Any,
    asset_id: str,
    name: str,
    shape: str,
    png_path: Path,
) -> None:
    """Register an item icon manifest with name + shape tags so /select
    can match by either the lowercased name or the shape descriptor."""
    manifest = make_manifest(
        asset_id=asset_id,
        kind=_ITEM_KIND,
        path=str(png_path),
        tags=[asset_id, shape],
        source="procedural",
        license="CC0",
        cost_usd=0.0,
        swap_safe=True,
    )
    catalog.add(asset_id, manifest)

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

from asset_manager.generators.procedural_sprite import generate_creature_token
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
    # Plains
    ("Bandit",          "plains",  (130, 90,  60,  255)),  # leather brown
    # Ruins
    ("Skeleton",        "ruins",   (230, 225, 205, 255)),  # bone
    ("Mutant",          "ruins",   (90,  140, 70,  255)),  # bile green
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
    )
    catalog.add(asset_id, manifest)

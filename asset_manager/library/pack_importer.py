"""Third-party asset pack importer.

Walks a directory of pack assets (GLB, FBX, OBJ, PNG, JPG) and registers
each as a catalog manifest with provenance metadata (source=pack, pack
name, license, redistribution flag). Idempotent: re-running on a pack
that's already imported updates existing entries in place rather than
duplicating.

Pack metadata flow:
  1. The caller supplies a `PackSpec` (or pack id from packs.yaml) that
     declares pack_name, license, redistribution flag, and an optional
     filename → manifest field mapping.
  2. The importer walks the pack directory, builds an asset_id from each
     filename via the spec's id rule, and infers `kind` from either the
     filename pattern or the immediate parent directory name.
  3. Each asset is registered in the catalog with the rich manifest fields
     so /select can score by tag and downstream cost-aware caching can
     reason about pack vs procedural vs AI sources.

Filename → manifest convention:
  Default rule (overridable per pack):
    asset_id = filename stem, lowercased, spaces → underscores
    kind     = parent directory name (e.g. "characters", "props", "tiles")
                  if not explicitly mapped, falls back to "pack_asset"
    tags     = filename tokens minus common noise words ("the", "a", "of")

  A `tag_strategy` can be set per pack to override this:
    "filename"   — split filename on _, -, space (default)
    "parent_dir" — use the parent directory name as the only tag
    "both"       — combine filename tokens AND parent dir as tags

License handling:
  Each PackSpec carries a `license_code` (matching the LICENSES.md table)
  and a `redistribution` boolean. These flow into the manifest so:
  - The asset catalog's HTML index can show license per asset.
  - A future export tool refuses to bundle assets with redistribution=False
    into a public artifact.
  - Synty paid packs are explicitly marked redistribution=False so even an
    accidental commit attempt would be caught by review.

Idempotency contract:
  - First import of a pack: every asset is registered with `generated_at` =
    now, `swap_safe=False` (since pack assets are hand-curated).
  - Re-import: existing entries are matched by asset_id and updated in
    place, but `generated_at` is preserved (we only refresh path/tags/
    metadata). Removing a pack file does NOT auto-prune the catalog entry
    (use Catalog.prune_missing_files for that).

Tests live in tests/test_pack_importer.py.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from asset_manager.library.manifest import make_manifest

logger = logging.getLogger(__name__)

# Asset extensions the importer recognizes. Anything else is skipped silently.
_ASSET_EXTENSIONS = {".glb", ".gltf", ".fbx", ".obj", ".png", ".jpg", ".jpeg"}

# Tokens stripped from filename-derived tags so we don't pollute the
# selector with noise words. Tweak the list as we encounter pack
# naming conventions in the wild.
_TAG_STOPWORDS = {"the", "a", "an", "of", "and", "or", "for", "with"}


@dataclass
class PackSpec:
    """Declares everything the importer needs to register a pack.

    Required:
      pack_name      Human-readable pack identifier (e.g. "KayKit Dungeon
                     Pack Remastered"). Stored verbatim in every manifest.
      pack_id        Stable short id used as a directory name and asset_id
                     prefix (e.g. "kaykit_dungeon"). Lowercase + underscores.
      license_code   License identifier matching LICENSES.md
                     (e.g. "KayKit_free", "CC0", "Synty_standard").
      redistribution Whether the asset files can be committed/distributed.
                     Free packs: True. Synty paid: False.

    Optional:
      kind_default   Fallback kind when neither the filename nor the parent
                     directory infers a kind. Default: "pack_asset".
      kind_overrides Map of parent-dir names to canonical kinds. Useful
                     when the pack uses non-standard folder names.
                     Example: {"Props": "prop", "Characters": "character"}
      tag_strategy   How to derive tags from filenames. One of "filename",
                     "parent_dir", "both". Default: "filename".
      asset_id_prefix Optional prefix prepended to every asset_id. Helps
                      avoid collisions across packs (e.g. "kaykit_" prefix
                      so KayKit "wall_corner.glb" doesn't collide with
                      Synty "wall_corner.glb").
    """
    pack_name: str
    pack_id: str
    license_code: str
    redistribution: bool
    kind_default: str = "pack_asset"
    kind_overrides: dict[str, str] = field(default_factory=dict)
    tag_strategy: str = "filename"
    asset_id_prefix: str | None = None


@dataclass
class ImportResult:
    """Counts and IDs of what an import_pack call did."""
    pack_id: str
    added: int = 0
    updated: int = 0
    skipped: int = 0
    asset_ids: list[str] = field(default_factory=list)


def import_pack(
    catalog: Any,
    pack_root: Path,
    spec: PackSpec,
) -> ImportResult:
    """Walk pack_root, register each recognized asset in the catalog.

    catalog must implement add(asset_id, manifest) and get(asset_id) — the
    same surface as Catalog. ImportResult is returned for caller logging /
    test assertions; the catalog itself is mutated as a side effect.

    The walk is recursive but stops at hidden directories (names starting
    with "."). This avoids descending into .git/ or .venv/ if a pack
    happens to be checked into a sibling repo.
    """
    result = ImportResult(pack_id=spec.pack_id)

    if not pack_root.exists():
        logger.warning("[pack_importer] pack_root does not exist: %s", pack_root)
        return result
    if not pack_root.is_dir():
        logger.warning("[pack_importer] pack_root is not a directory: %s", pack_root)
        return result

    for asset_path in _walk_pack(pack_root):
        try:
            asset_id, manifest = _build_manifest(asset_path, pack_root, spec)
        except Exception as e:
            logger.warning("[pack_importer] failed to build manifest for %s: %s", asset_path, e)
            result.skipped += 1
            continue

        existing = catalog.get(asset_id)
        if existing is not None:
            # Idempotent re-import: refresh path/tags/license but keep
            # the original generated_at so the timeline stays accurate.
            preserved_at = existing.get("generated_at")
            if preserved_at:
                manifest["generated_at"] = preserved_at
            catalog.add(asset_id, manifest)
            result.updated += 1
        else:
            catalog.add(asset_id, manifest)
            result.added += 1
        result.asset_ids.append(asset_id)

    logger.info(
        "[pack_importer] %s: added=%d updated=%d skipped=%d",
        spec.pack_id, result.added, result.updated, result.skipped,
    )
    return result


def _walk_pack(root: Path):
    """Yield asset files under root, skipping hidden dirs and unrecognized
    extensions. Sorted for deterministic ordering across runs."""
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() not in _ASSET_EXTENSIONS:
            continue
        yield path


def _build_manifest(
    asset_path: Path,
    pack_root: Path,
    spec: PackSpec,
) -> tuple[str, dict[str, Any]]:
    """Construct (asset_id, manifest_dict) for a single asset file."""
    rel = asset_path.relative_to(pack_root)
    parts = rel.parts

    # Asset ID: filename stem, lowercased, spaces/dashes → underscores,
    # optional pack prefix to avoid cross-pack collisions.
    raw_id = asset_path.stem.lower().replace(" ", "_").replace("-", "_")
    if spec.asset_id_prefix:
        asset_id = f"{spec.asset_id_prefix}{raw_id}"
    else:
        asset_id = raw_id

    # Kind: parent dir name override → parent dir name lowercased → default
    if len(parts) >= 2:
        parent_dir = parts[-2]
        kind = spec.kind_overrides.get(parent_dir, parent_dir.lower())
    else:
        kind = spec.kind_default

    # Tags: derived from the chosen strategy
    tags = _derive_tags(asset_path, parts, spec.tag_strategy)

    manifest = make_manifest(
        asset_id=asset_id,
        kind=kind,
        path=str(asset_path),
        tags=tags,
        source="pack",
        pack_name=spec.pack_name,
        license=spec.license_code,
        cost_usd=0.0,  # pack assets have no per-use cost (the pack was bought once)
        swap_safe=False,  # pack assets are hand-curated; never auto-overwrite
        redistribution=spec.redistribution,
    )
    return asset_id, manifest


def _derive_tags(asset_path: Path, parts: tuple, strategy: str) -> list[str]:
    """Build a tag list from the filename and/or parent directory."""
    out: set[str] = set()

    if strategy in ("filename", "both"):
        stem = asset_path.stem.lower()
        # Split on common separators and filter stopwords + numeric-only tokens
        for token in stem.replace("-", "_").replace(" ", "_").split("_"):
            token = token.strip()
            if not token or token in _TAG_STOPWORDS or token.isdigit():
                continue
            out.add(token)

    if strategy in ("parent_dir", "both") and len(parts) >= 2:
        parent = parts[-2].lower().replace(" ", "_").replace("-", "_")
        if parent and parent not in _TAG_STOPWORDS:
            out.add(parent)

    return sorted(out)

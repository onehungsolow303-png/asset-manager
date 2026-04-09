"""CLI: curate a LoRA training dataset from the catalog.

Picks N representative assets from the catalog and copies them to a
target directory ready for Stable Diffusion LoRA training. Solves
the "I have 13,800 tokens but training a LoRA needs 200-500 curated
images and picking them by hand is tedious" blocker.

Diversity strategy (round-robin across packs):
    1. Group assets by pack_name
    2. Iterate packs cyclically, picking one asset from each per round
    3. Stop when target count reached or all packs exhausted
    4. Within each pack, pick assets in sorted asset_id order so the
       output is deterministic across runs

This guarantees that even if one pack has 2,800 assets and another has
14, both contribute to the dataset. The trained LoRA learns from the
full visual range of the user's library, not just the largest pack.

Filters (all optional):
    --kind KIND          Only pick assets of this kind (creature_token,
                          portrait, ui_element, etc.)
    --source SOURCE      Only pick assets with this source (pack,
                          procedural, ai_2d, ai_3d)
    --license LICENSE    Only pick assets with this license_code
    --pack PATTERN       Only pick assets whose pack_name contains
                          this substring (case-insensitive). Repeatable.
    --max-per-pack N     Cap how many assets are pulled from any
                          single pack (default 50). Prevents one
                          dominant pack from skewing the trained style.

Output:
    --target-dir PATH    Where to copy the picked images. Default:
                          .shared/lora_training/dnd_style/source/
    --dataset-name NAME  Name used in the output dir + manifest.
                          Default: dnd_style.

A manifest CSV is written alongside the dataset listing what was
picked, including each asset's source pack and original path so the
user can audit / reproduce the selection.

Usage:
    python -m asset_manager.cli.curate_lora_dataset
    python -m asset_manager.cli.curate_lora_dataset --count 500 \\
        --kind portrait \\
        --max-per-pack 30 \\
        --dataset-name dnd_portraits

Symlinks vs copies:
    By default the curator COPIES files to avoid the dataset breaking
    if the source moves. --symlink uses symlinks instead (faster, less
    disk, but breaks if the source path changes).
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from asset_manager.library.catalog import DEFAULT_CATALOG_PATH, Catalog


DEFAULT_LORA_ROOT = Path("C:/Dev/.shared/lora_training")


def filter_assets(
    catalog: Catalog,
    *,
    kind: str | None = None,
    source: str | None = None,
    license_code: str | None = None,
    pack_patterns: list[str] | None = None,
) -> list[dict]:
    """Apply the optional filters and return matching catalog entries.

    Only image assets (PNG/JPG/etc.) are considered — 3D meshes don't
    train LoRAs. The check is path-based: any extension other than the
    common image set is dropped.
    """
    image_extensions = {".png", ".jpg", ".jpeg", ".webp"}
    pack_patterns = [p.lower() for p in (pack_patterns or [])]
    out = []
    for asset in catalog.all():
        path = str(asset.get("path") or "")
        if not path:
            continue
        if Path(path).suffix.lower() not in image_extensions:
            continue
        if kind and asset.get("kind") != kind:
            continue
        if source and asset.get("source") != source:
            continue
        if license_code and asset.get("license") != license_code:
            continue
        if pack_patterns:
            pack = (asset.get("pack_name") or "").lower()
            if not any(p in pack for p in pack_patterns):
                continue
        out.append(asset)
    return out


def round_robin_select(
    assets: list[dict],
    target_count: int,
    max_per_pack: int,
) -> list[dict]:
    """Pick `target_count` assets via round-robin across packs.

    Groups by pack_name, iterates packs in sorted order, picks one
    asset per pack per round. Continues until target_count is reached
    OR all packs are exhausted (or hit their max_per_pack cap).

    Within each pack, assets are picked in sorted asset_id order so
    the output is deterministic across runs.

    Returns a list of selected assets, length <= target_count.
    """
    if target_count <= 0 or not assets:
        return []

    by_pack: dict[str, list[dict]] = defaultdict(list)
    for a in assets:
        pack = a.get("pack_name") or "(no pack)"
        by_pack[pack].append(a)

    # Sort each pack's contents for determinism
    for pack in by_pack:
        by_pack[pack].sort(key=lambda a: a.get("asset_id", ""))

    pack_names = sorted(by_pack.keys())
    pack_taken: dict[str, int] = defaultdict(int)
    pack_indices: dict[str, int] = defaultdict(int)
    selected: list[dict] = []

    while len(selected) < target_count:
        progress_in_round = False
        for pack in pack_names:
            if len(selected) >= target_count:
                break
            if pack_taken[pack] >= max_per_pack:
                continue
            idx = pack_indices[pack]
            if idx >= len(by_pack[pack]):
                continue
            selected.append(by_pack[pack][idx])
            pack_indices[pack] += 1
            pack_taken[pack] += 1
            progress_in_round = True
        if not progress_in_round:
            # All packs exhausted or capped
            break

    return selected


def copy_to_dataset(
    selected: list[dict],
    dataset_dir: Path,
    use_symlinks: bool = False,
) -> tuple[int, int]:
    """Copy (or symlink) selected assets into dataset_dir.

    Returns (copied, skipped) counts. Skipped means the source file
    didn't exist or couldn't be opened.
    """
    dataset_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    skipped = 0
    for asset in selected:
        src = Path(str(asset.get("path", "")))
        if not src.exists() or not src.is_file():
            skipped += 1
            continue
        # Use the asset_id (sanitized) + original extension as the
        # destination filename so duplicates are impossible.
        asset_id = str(asset.get("asset_id", "asset"))
        safe_id = asset_id.replace("/", "_").replace("\\", "_").replace(":", "_")
        dst = dataset_dir / f"{safe_id}{src.suffix.lower()}"
        if dst.exists():
            copied += 1  # already there from a prior run
            continue
        try:
            if use_symlinks:
                # On Windows, symlink may need elevated privileges
                os.symlink(src, dst)
            else:
                shutil.copy2(src, dst)
            copied += 1
        except OSError:
            skipped += 1
    return copied, skipped


def write_manifest(
    selected: list[dict],
    manifest_path: Path,
) -> None:
    """Write a CSV manifest of what was picked."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["asset_id", "kind", "source", "pack_name", "license", "path", "tags"]
    with open(manifest_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for a in selected:
            w.writerow({
                "asset_id": a.get("asset_id", ""),
                "kind": a.get("kind", ""),
                "source": a.get("source", ""),
                "pack_name": a.get("pack_name") or "",
                "license": a.get("license", ""),
                "path": a.get("path", ""),
                "tags": ",".join(str(t) for t in (a.get("tags") or [])),
            })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Curate a LoRA training dataset from the catalog"
    )
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG_PATH))
    parser.add_argument(
        "--count",
        type=int,
        default=300,
        help="Target dataset size (default 300)",
    )
    parser.add_argument(
        "--max-per-pack",
        type=int,
        default=50,
        help="Max assets pulled from any single pack (default 50)",
    )
    parser.add_argument("--kind", default=None, help="Filter by asset kind")
    parser.add_argument("--source", default=None, help="Filter by source")
    parser.add_argument("--license", dest="license_code", default=None, help="Filter by license")
    parser.add_argument(
        "--pack",
        action="append",
        default=[],
        help="Pack name substring filter (repeatable)",
    )
    parser.add_argument(
        "--dataset-name",
        default="dnd_style",
        help="Name of the dataset; used in target dir + manifest filename",
    )
    parser.add_argument(
        "--target-dir",
        default=None,
        help="Override target directory (default: .shared/lora_training/<name>/source)",
    )
    parser.add_argument(
        "--lora-root",
        default=str(DEFAULT_LORA_ROOT),
        help="Root for LoRA training datasets",
    )
    parser.add_argument(
        "--symlink",
        action="store_true",
        help="Use symlinks instead of copies (faster but fragile)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be picked without copying anything",
    )
    args = parser.parse_args(argv)

    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        print(f"ERROR: catalog not found: {catalog_path}", file=sys.stderr)
        return 2

    catalog = Catalog(
        path=catalog_path,
        persist=False,
        auto_scan_baked=False,
        prune_on_load=False,
    )

    pool = filter_assets(
        catalog,
        kind=args.kind,
        source=args.source,
        license_code=args.license_code,
        pack_patterns=args.pack,
    )

    if not pool:
        print("no assets matched the filters", file=sys.stderr)
        return 1

    selected = round_robin_select(pool, args.count, args.max_per_pack)

    print(f"Selected {len(selected)} assets from {len(pool)} candidates")

    # Per-pack breakdown
    by_pack: dict[str, int] = defaultdict(int)
    for a in selected:
        by_pack[a.get("pack_name") or "(no pack)"] += 1
    print(f"Spread across {len(by_pack)} packs:")
    for pack, n in sorted(by_pack.items(), key=lambda x: -x[1])[:10]:
        print(f"  {pack[:50]:<50} {n:>4}")
    if len(by_pack) > 10:
        print(f"  ... and {len(by_pack) - 10} more packs")

    if args.dry_run:
        print()
        print("(dry-run — no files copied)")
        return 0

    if args.target_dir:
        dataset_dir = Path(args.target_dir)
    else:
        dataset_dir = Path(args.lora_root) / args.dataset_name / "source"

    print()
    print(f"Copying to {dataset_dir}...")
    copied, skipped = copy_to_dataset(selected, dataset_dir, use_symlinks=args.symlink)
    print(f"DONE: {copied} copied, {skipped} skipped")

    manifest_path = Path(args.lora_root) / args.dataset_name / "curation_manifest.csv"
    write_manifest(selected, manifest_path)
    print(f"Manifest: {manifest_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

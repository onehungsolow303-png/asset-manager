"""CLI: walk a pack root and inventory what's inside, without importing.

Use this BEFORE registering a pack into the catalog to see exactly
what's there. Useful for the Roll20 OneDrive library because:

  1. The library has 100+ subdirectories with cryptic names. The
     inventory tells you which ones contain images vs zips vs PSDs
     vs just metadata.

  2. OneDrive Files-On-Demand keeps bytes cloud-only by default. The
     inventory shows which files are MATERIALIZED (locally cached)
     vs PLACEHOLDER (cloud-only). You need to materialize before
     pack_importer can register them — or before Forever engine can
     read them.

  3. The output is a CSV you can sort/filter/decide-on without burning
     any catalog state. Iterate on which sub-packs to actually import
     before committing to anything.

Usage:
    python -m asset_manager.cli.inventory_packs <pack_root> [--csv path]

Example:
    python -m asset_manager.cli.inventory_packs \
        "C:/Users/bp303/OneDrive/Pictures/D&d UI assets/D&d/D&D Assets 1" \
        --csv inventory.csv

Output columns:
    sub_pack       — relative path of the subdirectory
    asset_count    — number of recognized image/3D files
    total_size_mb  — sum of file sizes in MB (counts placeholders as 0)
    materialized   — number of files actually present locally
    placeholder    — number of files that are OneDrive cloud-only
    extensions     — comma-separated list of unique extensions found
    notes          — flags like "EMPTY", "ALL_PLACEHOLDER", "MIXED"

The script is read-only and idempotent. Running it twice on the same
folder produces the same output. No catalog state is modified.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

# File extensions we consider as recognizable assets
_RECOGNIZED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",  # 2D
    ".glb",
    ".gltf",
    ".fbx",
    ".obj",
    ".blend",  # 3D
    ".psd",  # Photoshop source
}

# Windows file attributes (per win32 docs / GetFileAttributes)
# We check for FILE_ATTRIBUTE_OFFLINE (0x1000) and
# FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS (0x400000) to detect OneDrive
# cloud-only placeholder files. On non-Windows this check is a no-op.
_OFFLINE_ATTR = 0x1000
_RECALL_ATTR = 0x400000


def is_placeholder(path: Path) -> bool:
    """Return True if the file is a OneDrive Files-On-Demand placeholder.

    Heuristic: on Windows, check the OFFLINE / RECALL_ON_DATA_ACCESS
    file attribute bits. If neither is set, the file is materialized
    locally. On non-Windows the function returns False (no placeholders
    in scope).
    """
    if os.name != "nt":
        return False
    try:
        import ctypes

        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attrs == -1 or attrs == 0xFFFFFFFF:
            return False
        return bool(attrs & (_OFFLINE_ATTR | _RECALL_ATTR))
    except Exception:
        return False


def inventory_subpack(sub_root: Path) -> dict:
    """Inventory a single sub-pack directory."""
    asset_count = 0
    total_size = 0
    materialized = 0
    placeholder = 0
    extensions: set[str] = set()

    for path in sub_root.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in _RECOGNIZED_EXTENSIONS:
            continue
        asset_count += 1
        extensions.add(suffix)

        if is_placeholder(path):
            placeholder += 1
        else:
            materialized += 1
            try:
                total_size += path.stat().st_size
            except OSError:
                pass

    notes = []
    if asset_count == 0:
        notes.append("EMPTY")
    elif placeholder == asset_count:
        notes.append("ALL_PLACEHOLDER")
    elif materialized == asset_count:
        notes.append("ALL_MATERIALIZED")
    else:
        notes.append("MIXED")

    return {
        "sub_pack": sub_root.name,
        "asset_count": asset_count,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "materialized": materialized,
        "placeholder": placeholder,
        "extensions": ",".join(sorted(extensions)),
        "notes": "|".join(notes),
    }


def inventory_pack_root(pack_root: Path) -> list[dict]:
    """Walk one level deep under pack_root, inventory each subdirectory."""
    if not pack_root.exists() or not pack_root.is_dir():
        print(
            f"ERROR: pack root does not exist or is not a directory: {pack_root}", file=sys.stderr
        )
        return []

    rows: list[dict] = []
    for entry in sorted(pack_root.iterdir()):
        if entry.is_dir() and not entry.name.startswith("."):
            row = inventory_subpack(entry)
            rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inventory a pack root without importing it")
    parser.add_argument(
        "pack_root",
        help="Top-level directory containing sub-pack directories",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Optional CSV output path. If omitted, prints to stdout.",
    )
    args = parser.parse_args(argv)

    pack_root = Path(args.pack_root)
    rows = inventory_pack_root(pack_root)

    if not rows:
        return 1

    if args.csv:
        out_path = Path(args.csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {len(rows)} rows to {out_path}")
    else:
        # Pretty print to stdout
        widths = {k: max(len(str(r.get(k, ""))) for r in rows + [{k: k}]) for k in rows[0].keys()}
        # Header
        print(" | ".join(k.ljust(widths[k]) for k in rows[0].keys()))
        print("-+-".join("-" * widths[k] for k in rows[0].keys()))
        # Rows
        for row in rows:
            print(" | ".join(str(row[k]).ljust(widths[k]) for k in row.keys()))
        # Summary
        total_assets = sum(r["asset_count"] for r in rows)
        total_size = sum(r["total_size_mb"] for r in rows)
        total_materialized = sum(r["materialized"] for r in rows)
        total_placeholder = sum(r["placeholder"] for r in rows)
        print()
        print(
            f"TOTAL: {len(rows)} sub-packs, {total_assets} assets, "
            f"{total_size:.1f} MB materialized, "
            f"{total_materialized} files local, {total_placeholder} placeholder"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

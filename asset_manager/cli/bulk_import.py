"""CLI: bulk-import a multi-sub-pack asset library into the catalog.

Walks a parent directory and imports each immediate subdirectory as
a separate pack via the existing pack_importer. Designed for the
Roll20 / Forgotten Adventures scenario where the user has 90+ small
sub-packs in one parent folder and wants to register them all in the
catalog with one command.

Why each sub-pack gets its own pack_id:
    Two unrelated packs might both contain "wolf.png" — different art,
    same filename. With ONE big import-the-whole-tree call, both would
    collapse into a single asset_id "wolf" and the second would
    overwrite the first. Per-sub-pack imports give each its own
    asset_id_prefix derived from the sub-pack folder name, avoiding
    cross-pack collisions.

Filtering options:
    --max-size-mb N      Skip sub-packs whose total recursive size
                          exceeds N megabytes. Useful for excluding
                          giant tile variant collections that would
                          bloat the catalog.
    --exclude PATTERN    Skip sub-packs whose name matches the substring
                          (case-insensitive). Can be passed multiple
                          times.
    --include PATTERN    ONLY import sub-packs whose name matches the
                          substring. Inverse of --exclude.
    --dry-run            Print what WOULD be imported without making
                          any catalog changes.

The CLI uses the in-process pack_importer module directly (not the
HTTP endpoint) for speed — this avoids per-import HTTP overhead when
processing dozens of sub-packs back-to-back. Catalog mutations persist
through the shared on-disk JSON file. After running, restart Asset
Manager to pick up the new state in its in-memory catalog.

Usage:
    python -m asset_manager.cli.bulk_import <parent_dir> [options]

    python -m asset_manager.cli.bulk_import \\
        "C:/Pictures/Assets/D&d UI assets/D&d/D&D Assets 1" \\
        --license Roll20_marketplace_personal \\
        --no-redistribution \\
        --asset-id-prefix-template "roll20_{slug}_" \\
        --max-size-mb 700 \\
        --exclude Core_Mapmaking \\
        --exclude .dungeondraft_pack
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from asset_manager.library.catalog import DEFAULT_CATALOG_PATH, Catalog
from asset_manager.library.pack_importer import PackSpec, import_pack


def slugify(name: str) -> str:
    """Convert a folder name to a safe asset_id_prefix slug."""
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s or "pack"


def directory_size_mb(root: Path) -> float:
    """Recursive size of a directory in megabytes."""
    total = 0
    try:
        for p in root.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
            except OSError:
                pass
    except OSError:
        pass
    return total / (1024 * 1024)


def list_subpacks(parent: Path) -> list[Path]:
    """Return immediate subdirectories of parent, sorted."""
    if not parent.exists() or not parent.is_dir():
        return []
    return sorted(p for p in parent.iterdir() if p.is_dir() and not p.name.startswith("."))


def should_skip(
    sub_pack: Path,
    size_mb: float,
    max_size_mb: float | None,
    exclude_patterns: list[str],
    include_patterns: list[str],
) -> tuple[bool, str]:
    """Decide whether a sub-pack should be skipped + reason."""
    name = sub_pack.name
    name_lower = name.lower()

    if include_patterns:
        if not any(p.lower() in name_lower for p in include_patterns):
            return True, "not in --include list"

    for pat in exclude_patterns:
        if pat.lower() in name_lower:
            return True, f"matches --exclude {pat!r}"

    if max_size_mb is not None and size_mb > max_size_mb:
        return True, f"size {size_mb:.0f} MB > max {max_size_mb:.0f} MB"

    return False, ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bulk-import sub-packs from a parent directory"
    )
    parser.add_argument("parent", help="Parent directory containing sub-pack folders")
    parser.add_argument(
        "--catalog",
        default=str(DEFAULT_CATALOG_PATH),
        help="Path to the catalog JSON file",
    )
    parser.add_argument(
        "--pack-id-prefix",
        default="",
        help="Prefix prepended to each sub-pack's pack_id (e.g., 'roll20_')",
    )
    parser.add_argument(
        "--asset-id-prefix-template",
        default="{slug}_",
        help="Template for asset_id_prefix per sub-pack. {slug} is replaced "
             "with the lowercased+slugified folder name.",
    )
    parser.add_argument(
        "--license",
        default="unknown",
        help="License code for every imported pack",
    )
    parser.add_argument(
        "--no-redistribution",
        action="store_true",
        help="Mark imported packs as redistribution=false (Roll20-style)",
    )
    parser.add_argument(
        "--kind-default",
        default="pack_asset",
        help="Default kind for files whose parent dir doesn't infer one",
    )
    parser.add_argument(
        "--tag-strategy",
        default="both",
        choices=("filename", "parent_dir", "both"),
        help="Tag derivation strategy",
    )
    parser.add_argument(
        "--max-size-mb",
        type=float,
        default=None,
        help="Skip sub-packs larger than N megabytes",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Skip sub-packs whose name contains this substring (repeatable)",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Only import sub-packs whose name contains this substring (repeatable)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be imported without making any catalog changes",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-pack progress lines",
    )
    args = parser.parse_args(argv)

    parent = Path(args.parent)
    if not parent.exists() or not parent.is_dir():
        print(f"ERROR: parent not a directory: {parent}", file=sys.stderr)
        return 2

    sub_packs = list_subpacks(parent)
    if not sub_packs:
        print(f"no sub-packs found in {parent}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Found {len(sub_packs)} sub-packs in {parent}")
        print()

    # Load the catalog from disk. Persist=True so each import call
    # writes through to the JSON file. Auto-scan disabled to avoid
    # blowing up the import time on a 28GB tree.
    catalog: Catalog | None = None
    if not args.dry_run:
        catalog = Catalog(
            path=Path(args.catalog),
            persist=True,
            auto_scan_baked=False,
            prune_on_load=False,
        )

    total_imported = 0
    total_skipped_packs = 0
    total_added = 0
    total_updated = 0
    total_assets_skipped = 0

    for i, sub in enumerate(sub_packs, start=1):
        size_mb = directory_size_mb(sub)
        skip, reason = should_skip(
            sub, size_mb, args.max_size_mb, args.exclude, args.include
        )

        if skip:
            total_skipped_packs += 1
            if not args.quiet:
                print(f"[{i:>3}/{len(sub_packs)}] {sub.name:<55} SKIP ({reason})")
            continue

        slug = slugify(sub.name)
        pack_id = f"{args.pack_id_prefix}{slug}"
        pack_name = sub.name
        asset_id_prefix = args.asset_id_prefix_template.format(slug=slug)

        if args.dry_run:
            if not args.quiet:
                print(
                    f"[{i:>3}/{len(sub_packs)}] {sub.name:<55} "
                    f"DRY-RUN ({size_mb:.1f} MB, prefix={asset_id_prefix})"
                )
            continue

        spec = PackSpec(
            pack_id=pack_id,
            pack_name=pack_name,
            license_code=args.license,
            redistribution=not args.no_redistribution,
            kind_default=args.kind_default,
            tag_strategy=args.tag_strategy,
            asset_id_prefix=asset_id_prefix,
        )

        try:
            result = import_pack(catalog, sub, spec)
        except Exception as e:
            if not args.quiet:
                print(f"[{i:>3}/{len(sub_packs)}] {sub.name:<55} FAIL: {e}")
            continue

        total_imported += 1
        total_added += result.added
        total_updated += result.updated
        total_assets_skipped += result.skipped

        if not args.quiet:
            print(
                f"[{i:>3}/{len(sub_packs)}] {sub.name:<55} "
                f"OK +{result.added:<5} ~{result.updated:<5} "
                f"({size_mb:.0f} MB)"
            )

    if not args.quiet:
        print()
        print(
            f"DONE: {total_imported} sub-packs imported, "
            f"{total_skipped_packs} skipped. "
            f"+{total_added} new, ~{total_updated} updated, "
            f"-{total_assets_skipped} skipped assets."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

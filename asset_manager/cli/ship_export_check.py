"""CLI: report which catalog assets are NOT safe to ship commercially.

Walks the asset catalog and produces a "ship readiness" report flagging
every entry with redistribution=false. These are assets we use during
development (Roll20 marketplace originals, anything with a personal-use
license) that MUST be replaced before a public commercial game ship.

Why this exists:
    The user's pipeline imports Roll20 marketplace assets directly so
    Forever engine has visible D&D-quality art during playtesting.
    Those assets are licensed for personal VTT use, NOT for inclusion
    in a third-party commercial game build. The replacement strategy
    is to substitute each one with either:

      1. A Nano Banana derivative (substantial modification → user owns)
      2. A LoRA-generated original (trained on the user's curated subset)
      3. A Tripo3D-generated 3D mesh rendered to 2D from style references

    This CLI tells the user exactly how many "must-replace" assets
    they have left, broken down by license/pack/kind so they can
    prioritize the substitution work.

Usage:
    python -m asset_manager.cli.ship_export_check
    python -m asset_manager.cli.ship_export_check --csv report.csv
    python -m asset_manager.cli.ship_export_check --quiet  # exit code only

Exit codes:
    0   no must-replace assets in catalog (ship-clean)
    1   must-replace assets present (count printed to stderr)
    2   error reading catalog

The --quiet flag is intended for CI / pre-ship hooks: integrate with
a build pipeline so the public commercial build refuses to bundle
the catalog if any restricted assets are still registered.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

from asset_manager.library.catalog import DEFAULT_CATALOG_PATH, Catalog


def find_must_replace(catalog: Catalog) -> list[dict]:
    """Return every catalog entry where redistribution is False."""
    return [
        a for a in catalog.all()
        if not a.get("redistribution", True)
    ]


def summarize(must_replace: list[dict]) -> dict:
    """Build a summary structure for human-readable reporting."""
    by_license = Counter(a.get("license", "unknown") for a in must_replace)
    by_pack = Counter(a.get("pack_name") or "(no pack)" for a in must_replace)
    by_kind = Counter(a.get("kind", "unknown") for a in must_replace)
    by_source = Counter(a.get("source", "unknown") for a in must_replace)

    return {
        "total": len(must_replace),
        "by_license": dict(by_license),
        "by_pack": dict(by_pack),
        "by_kind": dict(by_kind),
        "by_source": dict(by_source),
    }


def write_csv_report(must_replace: list[dict], out_path: Path) -> None:
    """Write a CSV with one row per must-replace asset."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "asset_id", "kind", "source", "pack_name", "license",
        "cost_usd", "path", "tags", "biome", "generated_at",
    ]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for a in must_replace:
            writer.writerow({
                "asset_id": a.get("asset_id", ""),
                "kind": a.get("kind", ""),
                "source": a.get("source", ""),
                "pack_name": a.get("pack_name") or "",
                "license": a.get("license", ""),
                "cost_usd": a.get("cost_usd", 0.0),
                "path": a.get("path", ""),
                "tags": ",".join(str(t) for t in (a.get("tags") or [])),
                "biome": a.get("biome", ""),
                "generated_at": a.get("generated_at", ""),
            })


def print_human_report(summary: dict, must_replace: list[dict], limit: int = 10) -> None:
    """Print a human-readable summary to stdout.

    Uses ASCII-only output so the report works in Windows cp1252 consoles.
    Unicode pretty marks (checkmarks, arrows) crash on `print()` when
    stdout's encoding is cp1252 and the user hasn't run `chcp 65001`.
    """
    total = summary["total"]
    print(f"Ship-readiness report: {total} assets flagged as must-replace")
    print()

    if total == 0:
        print("[OK] Catalog is ship-clean. All assets have redistribution=True.")
        return

    print("Breakdown by license:")
    for lic, n in sorted(summary["by_license"].items(), key=lambda x: -x[1]):
        print(f"  {lic:<40} {n:>5}")
    print()

    print("Breakdown by pack:")
    for pack, n in sorted(summary["by_pack"].items(), key=lambda x: -x[1]):
        print(f"  {pack:<60} {n:>5}")
    print()

    print("Breakdown by kind:")
    for kind, n in sorted(summary["by_kind"].items(), key=lambda x: -x[1]):
        print(f"  {kind:<25} {n:>5}")
    print()

    if limit and len(must_replace) > 0:
        print(f"First {min(limit, len(must_replace))} entries (asset_id, kind, license):")
        for a in must_replace[:limit]:
            print(
                f"  {a.get('asset_id','?')[:40]:<40} "
                f"{a.get('kind','?')[:15]:<15} "
                f"{a.get('license','?')}"
            )
        if len(must_replace) > limit:
            print(f"  ... and {len(must_replace) - limit} more")
    print()
    print("To resolve: substitute each must-replace asset with one of:")
    print("  1. A Nano Banana derivative (substantial modification)")
    print("  2. A LoRA-generated original (trained on curated D&D subset)")
    print("  3. A Tripo3D-generated 3D mesh rendered to 2D from style refs")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report catalog assets that must be replaced before "
                    "shipping a commercial build"
    )
    parser.add_argument(
        "--catalog",
        default=str(DEFAULT_CATALOG_PATH),
        help="Path to the catalog JSON file",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Optional CSV output path with full per-asset detail",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout; exit 1 if any must-replace assets exist",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max sample entries to show in the human report (default 10)",
    )
    args = parser.parse_args(argv)

    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        print(f"ERROR: catalog not found: {catalog_path}", file=sys.stderr)
        return 2

    try:
        # Load with auto_scan_baked=False so we read exactly what's on disk
        # without rescanning. ship_export_check is a read-only audit, not
        # a refresh.
        catalog = Catalog(
            path=catalog_path,
            persist=False,  # don't write back even if migration touches it
            auto_scan_baked=False,
            prune_on_load=False,
        )
    except Exception as e:
        print(f"ERROR: failed to load catalog: {e}", file=sys.stderr)
        return 2

    must_replace = find_must_replace(catalog)
    summary = summarize(must_replace)

    if args.csv:
        write_csv_report(must_replace, Path(args.csv))
        if not args.quiet:
            print(f"wrote CSV report to {args.csv}")
            print()

    if args.quiet:
        if must_replace:
            print(
                f"{len(must_replace)} must-replace assets in catalog",
                file=sys.stderr,
            )
            return 1
        return 0

    print_human_report(summary, must_replace, limit=args.limit)
    return 1 if must_replace else 0


if __name__ == "__main__":
    raise SystemExit(main())

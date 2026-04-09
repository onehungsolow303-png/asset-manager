"""CLI: register a Tripo3D-generated 3D model in the asset catalog.

After generating a model via the DCC Bridge and it lands in
Forever engine/Assets/GeneratedModels/, this CLI registers it
in the Asset Manager catalog with proper provenance so the
deterministic protocol knows it exists and never re-generates it.

Why this exists:
    The DCC Bridge drops GLB files into the Unity project but
    doesn't talk to our Asset Manager catalog. Without registration,
    the source_decision router doesn't know the model exists and
    would try to generate it again on the next request. This CLI
    bridges that gap.

Usage:
    # Register a single model:
    python -m asset_manager.cli.register_3d_model garth \
        "C:/Dev/Forever engine/Assets/GeneratedModels/Characters/garth.glb" \
        --kind character --tags garth,npc,dwarf,camp_leader

    # Register all GLBs in a directory:
    python -m asset_manager.cli.register_3d_model --scan-dir \
        "C:/Dev/Forever engine/Assets/GeneratedModels/Characters/" \
        --kind character

    # List all registered 3D models:
    python -m asset_manager.cli.register_3d_model --list
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from asset_manager.library.catalog import DEFAULT_CATALOG_PATH, Catalog
from asset_manager.library.manifest import make_manifest


_3D_EXTENSIONS = {".glb", ".gltf", ".fbx", ".obj"}


def register_model(
    catalog: Catalog,
    asset_id: str,
    path: Path,
    kind: str = "character",
    tags: list[str] | None = None,
    source_image: str | None = None,
) -> bool:
    """Register a single 3D model in the catalog.

    Returns True if added/updated, False if the file doesn't exist.
    """
    if not path.exists():
        print(f"  SKIP: file not found: {path}", file=sys.stderr)
        return False

    manifest = make_manifest(
        asset_id=asset_id,
        kind=kind,
        path=str(path),
        tags=tags or [asset_id],
        source="ai_3d",
        pack_name="tripo3d_dcc_bridge",
        license="Tripo3D_owned",
        cost_usd=0.30,  # approximate per-model cost
        swap_safe=False,  # hand-curated via DCC Bridge, never auto-overwrite
        redistribution=True,  # user owns generated models per Tripo ToS
    )

    # If we know the source image that was fed to Tripo, record it
    # as the prompt field for provenance tracking
    if source_image:
        manifest["prompt"] = f"image-to-3D from: {source_image}"

    catalog.add(asset_id, manifest)
    return True


def scan_directory(
    catalog: Catalog,
    directory: Path,
    kind: str = "character",
    prefix: str = "",
) -> int:
    """Scan a directory for GLB/FBX files and register each one.

    asset_id is derived from the filename stem (lowercase + underscores).
    Returns the count of newly registered models.
    """
    if not directory.exists() or not directory.is_dir():
        print(f"ERROR: not a directory: {directory}", file=sys.stderr)
        return 0

    registered = 0
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _3D_EXTENSIONS:
            continue

        asset_id = prefix + path.stem.lower().replace(" ", "_").replace("-", "_")
        if register_model(catalog, asset_id, path, kind=kind):
            print(f"  + {asset_id} ({path.suffix}, {path.stat().st_size / 1024:.0f} KB)")
            registered += 1

    return registered


def list_3d_models(catalog: Catalog) -> int:
    """List all catalog entries with source=ai_3d."""
    models = [a for a in catalog.all() if a.get("source") == "ai_3d"]
    if not models:
        print("No 3D models registered yet.")
        return 0

    print(f"Registered 3D models: {len(models)}")
    print()
    for m in sorted(models, key=lambda x: x.get("asset_id", "")):
        print(f"  {m.get('asset_id','?'):30} {m.get('kind','?'):15} {m.get('path','')[:60]}")
    return len(models)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Register Tripo3D-generated 3D models in the asset catalog"
    )
    parser.add_argument(
        "asset_id",
        nargs="?",
        help="Semantic asset ID (e.g., garth, thalia, wolf_alpha)",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to the GLB/FBX/OBJ file",
    )
    parser.add_argument("--kind", default="character", help="Asset kind (default: character)")
    parser.add_argument("--tags", default=None, help="Comma-separated tags")
    parser.add_argument("--source-image", default=None, help="Path to the 2D image used as input")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG_PATH))
    parser.add_argument(
        "--scan-dir",
        default=None,
        help="Scan a directory for all GLB/FBX files and register each",
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="Prefix for asset_id when scanning (e.g., 'tripo_')",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all registered 3D models",
    )
    args = parser.parse_args(argv)

    catalog = Catalog(
        path=Path(args.catalog),
        persist=True,
        auto_scan_baked=False,
        prune_on_load=False,
    )

    if args.list:
        list_3d_models(catalog)
        return 0

    if args.scan_dir:
        count = scan_directory(
            catalog,
            Path(args.scan_dir),
            kind=args.kind,
            prefix=args.prefix,
        )
        print(f"\nRegistered {count} 3D models")
        return 0

    if not args.asset_id or not args.path:
        parser.error("provide asset_id + path, or use --scan-dir or --list")
        return 1

    tags = args.tags.split(",") if args.tags else None
    success = register_model(
        catalog,
        args.asset_id,
        Path(args.path),
        kind=args.kind,
        tags=tags,
        source_image=args.source_image,
    )

    if success:
        print(f"Registered: {args.asset_id}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

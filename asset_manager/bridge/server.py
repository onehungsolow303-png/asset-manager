"""Asset Manager HTTP bridge - FastAPI app on port 7801."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from asset_manager import __version__
from asset_manager.bridge.schemas import (
    AssetSelectionRequest,
    AssetSelectionResponse,
    CatalogResponse,
    GenerationRequest,
    GenerationResponse,
)
from asset_manager.generators.procedural_sprite import (
    generate_creature_token,
    generate_item_icon,
)
from asset_manager.generators.texture import (
    generate_terrain_texture,
    generate_tileset,
)
from asset_manager.library.catalog import DEFAULT_BAKED_ROOT, Catalog
from asset_manager.library.html_index import regenerate_index
from asset_manager.library.manifest import make_manifest
from asset_manager.library.pack_importer import PackSpec, import_pack
from asset_manager.library.seed import (
    seed_default_creature_tokens,
    seed_default_item_icons,
)
from asset_manager.library.storage import Storage
from asset_manager.selectors.selector import Selector

app = FastAPI(title="Asset Manager", version=__version__)
_catalog = Catalog()
_selector = Selector(_catalog)
_storage = Storage()

# Seed the library with default creature tokens AND item icons on
# startup so Forever engine's BattleManager.RequestEnemySprites and
# the inventory/dialogue UI both get visible asset hits without the
# user having to manually bake anything. Idempotent: skips anything
# whose PNG already exists. See library/seed.py for the lists.
seed_default_creature_tokens(_catalog)
seed_default_item_icons(_catalog)


_INDEX_PATH = DEFAULT_BAKED_ROOT / "index.html"


def _refresh_html_index() -> None:
    """Regenerate the HTML asset index after any catalog mutation.

    Best-effort: failures are logged but never crash the bridge — the
    index is a convenience tool, not a correctness boundary. Wrapped
    in a function so /generate, /bake, and /import_pack can all call
    the same code path.
    """
    try:
        regenerate_index(_catalog, _INDEX_PATH)
    except Exception as e:  # boundary - log and continue
        import logging
        logging.getLogger(__name__).warning(
            "[server] HTML index regeneration failed: %s", e
        )


# Generate the initial HTML index now that seeds have run, so the user
# can browse the post-seed catalog without making any HTTP calls first.
_refresh_html_index()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "asset_manager", "version": __version__}


@app.get("/catalog", response_model=CatalogResponse)
def catalog() -> CatalogResponse:
    assets = _catalog.all()
    return CatalogResponse(count=len(assets), assets=assets)


@app.post("/select", response_model=AssetSelectionResponse)
def select(req: AssetSelectionRequest) -> AssetSelectionResponse:
    hit = _selector.select(req.model_dump())
    if hit is None:
        return AssetSelectionResponse(
            found=False,
            notes=["miss: no asset matched (Phase 2 stub - selector always misses)"],
        )
    return AssetSelectionResponse(
        found=True,
        asset_id=hit.get("asset_id"),
        path=hit.get("path"),
        manifest=hit,
    )


def _color(spec: dict[str, Any]) -> tuple[int, int, int, int]:
    """Convert a JSON [R, G, B, A] array to a Python RGBA tuple."""
    c = spec.get("color", [255, 255, 255, 255])
    return (int(c[0]), int(c[1]), int(c[2]), int(c[3]) if len(c) > 3 else 255)


def _handle_creature_token(req: GenerationRequest) -> tuple[str, Path]:
    color = _color(req.constraints)
    size = int(req.constraints.get("size", 32))
    asset_id = f"token_{uuid.uuid4().hex[:8]}"
    out = _storage.path_for("creature_token", asset_id, ext="png")
    generate_creature_token(color, size=size, out_path=out)
    return asset_id, out


def _handle_item_icon(req: GenerationRequest) -> tuple[str, Path]:
    color = _color(req.constraints)
    size = int(req.constraints.get("size", 16))
    shape = str(req.constraints.get("shape", "square"))
    asset_id = f"icon_{uuid.uuid4().hex[:8]}"
    out = _storage.path_for("item_icon", asset_id, ext="png")
    generate_item_icon(color, shape=shape, size=size, out_path=out)
    return asset_id, out


def _handle_terrain(req: GenerationRequest) -> tuple[str, Path]:
    width = int(req.constraints.get("width", 32))
    height = int(req.constraints.get("height", 32))
    floor = _color({"color": req.constraints.get("floor_color", [100, 80, 60, 255])})
    wall = _color({"color": req.constraints.get("wall_color", [50, 40, 30, 255])})
    seed = int(req.constraints.get("seed", 42))
    asset_id = f"terrain_{uuid.uuid4().hex[:8]}"
    out = _storage.path_for("terrain", asset_id, ext="png")
    generate_terrain_texture(width, height, floor, wall, seed=seed, out_path=out)
    return asset_id, out


def _handle_tileset(req: GenerationRequest) -> tuple[str, Path]:
    tile_size = int(req.constraints.get("tile_size", 16))
    tiles_per_row = int(req.constraints.get("tiles_per_row", 4))
    raw_colors = req.constraints.get("tile_colors", [[100, 0, 0, 255]])
    colors = [_color({"color": c}) for c in raw_colors]
    seed = int(req.constraints.get("seed", 42))
    asset_id = f"tileset_{uuid.uuid4().hex[:8]}"
    out = _storage.path_for("tileset", asset_id, ext="png")
    generate_tileset(tile_size, tiles_per_row, colors, seed=seed, out_path=out)
    return asset_id, out


_GENERATION_HANDLERS = {
    "creature_token": _handle_creature_token,
    "item_icon": _handle_item_icon,
    "terrain": _handle_terrain,
    "tileset": _handle_tileset,
}


@app.post("/generate", response_model=GenerationResponse)
def generate(req: GenerationRequest) -> GenerationResponse:
    handler = _GENERATION_HANDLERS.get(req.kind)
    if handler is None:
        return GenerationResponse(
            accepted=False,
            notes=[
                f"unknown kind: {req.kind!r} (supported: {sorted(_GENERATION_HANDLERS.keys())})"
            ],
        )
    try:
        asset_id, out_path = handler(req)
    except Exception as e:  # boundary - log and return failure
        return GenerationResponse(accepted=False, notes=[f"generation failed: {e}"])

    # Auto-bake into the catalog so subsequent /select calls find it.
    manifest = make_manifest(
        asset_id=asset_id,
        kind=req.kind,
        path=str(out_path),
        source="procedural",
        license="CC0",
        cost_usd=0.0,
        prompt=req.prompt,
    )
    _catalog.add(asset_id, manifest)
    _refresh_html_index()

    return GenerationResponse(
        accepted=True,
        asset_id=asset_id,
        path=str(out_path),
        notes=[],
    )


@app.post("/validate")
def validate(payload: dict) -> dict:
    image_path = payload.get("path")
    if not image_path:
        return {"passed": False, "notes": ["missing 'path' field"]}
    return {
        "passed": False,
        "score": 0.0,
        "notes": ["Phase 2 stub: validator not yet exercised against real assets"],
    }


@app.post("/bake")
def bake(payload: dict) -> dict:
    """Register a previously-generated asset in the catalog."""
    asset_id = payload.get("asset_id")
    if not asset_id:
        return {"baked": False, "notes": ["missing 'asset_id' field"]}
    manifest = make_manifest(
        asset_id=asset_id,
        kind=payload.get("kind", "unknown"),
        path=payload.get("path", ""),
    )
    _catalog.add(asset_id, manifest)
    _refresh_html_index()
    return {"baked": True, "asset_id": asset_id}


@app.post("/import_pack")
def import_pack_endpoint(payload: dict) -> dict:
    """Import a third-party asset pack into the catalog.

    Expected payload (all fields except notes are required):
        {
            "pack_id": "kaykit_dungeon",
            "pack_name": "KayKit Dungeon Pack Remastered",
            "license_code": "KayKit_free",
            "redistribution": true,
            "local_path": "C:/Dev/.shared/baked/packs/kaykit/dungeon",
            "asset_id_prefix": "kaykit_dungeon_",
            "tag_strategy": "both",
            "kind_default": "dungeon_tile",
            "kind_overrides": {"Walls": "dungeon_wall", "Props": "dungeon_prop"}
        }

    Returns:
        {
            "imported": true,
            "pack_id": "kaykit_dungeon",
            "added": 47,
            "updated": 0,
            "skipped": 0,
            "asset_ids": [...]
        }

    Idempotent: re-running on a pack already imported updates entries
    in place rather than duplicating. The endpoint does NOT download
    the pack — local_path must already exist on disk (manual
    download for Synty paid packs, scriptable installer for free
    packs in a future enhancement).
    """
    pack_id = payload.get("pack_id")
    pack_name = payload.get("pack_name")
    local_path = payload.get("local_path")
    license_code = payload.get("license_code", "unknown")
    redistribution = bool(payload.get("redistribution", True))

    if not (pack_id and pack_name and local_path):
        return {
            "imported": False,
            "notes": ["missing required field: pack_id, pack_name, local_path"],
        }

    pack_root = Path(local_path)
    if not pack_root.exists():
        return {
            "imported": False,
            "notes": [
                f"local_path does not exist: {local_path}. "
                "For free packs, run the pack installer first. "
                "For paid Synty packs, download from Unity Asset Store and extract."
            ],
        }

    spec = PackSpec(
        pack_id=pack_id,
        pack_name=pack_name,
        license_code=license_code,
        redistribution=redistribution,
        kind_default=payload.get("kind_default", "pack_asset"),
        kind_overrides=payload.get("kind_overrides", {}) or {},
        tag_strategy=payload.get("tag_strategy", "filename"),
        asset_id_prefix=payload.get("asset_id_prefix"),
    )

    result = import_pack(_catalog, pack_root, spec)
    _refresh_html_index()

    return {
        "imported": True,
        "pack_id": result.pack_id,
        "added": result.added,
        "updated": result.updated,
        "skipped": result.skipped,
        "asset_ids": result.asset_ids,
    }

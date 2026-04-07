"""Asset Manager HTTP bridge - FastAPI app on port 7801.

Endpoints (Phase 2 stubs):
    GET  /health
    GET  /catalog
    POST /select
    POST /generate
    POST /validate
    POST /bake
"""
from __future__ import annotations

from fastapi import FastAPI

from asset_manager import __version__
from asset_manager.bridge.schemas import (
    AssetSelectionRequest,
    AssetSelectionResponse,
    CatalogResponse,
    GenerationRequest,
    GenerationResponse,
)
from asset_manager.library.catalog import Catalog
from asset_manager.selectors.selector import Selector

app = FastAPI(title="Asset Manager", version=__version__)
_catalog = Catalog()
_selector = Selector(_catalog)


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


@app.post("/generate", response_model=GenerationResponse)
def generate(req: GenerationRequest) -> GenerationResponse:
    return GenerationResponse(
        accepted=False,
        notes=[
            "Phase 2 stub: generation gateway not yet wired. "
            "See spec §14 follow-up #1 and the gateway/ stubs."
        ],
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
    return {
        "baked": False,
        "notes": ["Phase 2 stub: baking pipeline not yet wired"],
    }

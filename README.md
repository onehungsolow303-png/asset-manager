# Asset Manager - Library, Selector, Generator, AI Gateway

The sole writer of the asset library used by Forever engine. Catalogs every asset, selects the right one for a given context, generates new ones procedurally or via AI image models, validates AI-generated output before baking, exposes everything over HTTP on port 7801.

**Spec:** `C:\Dev\.shared\docs\superpowers\specs\2026-04-06-three-module-consolidation-design.md`

## Status

Phase 2 of the three-module pivot. Currently a **scaffolded service** with stub generators, stub selectors, stub gateways, and the salvaged `border_detect/` + `quality_metrics.py` from Gut It Out wired into `validators/`. Real procedural generators, AI gateways, and library persistence are spec §14 follow-ups.

## What this used to be

Before the pivot, this directory was the legacy "Map Generator" - a Python pygame project plus 21 PCG agents. The pygame viewer has been archived to `C:\Dev\_archive\mapgen-pygame-viewer\`. The 21 PCG agents have been kept and moved to `asset_manager/generators/pcg/`.

## Quick start

```bash
cd "C:/Dev/Asset Manager"
python -m venv .venv
source .venv/Scripts/activate
pip install -e ".[dev]"
uvicorn asset_manager.bridge.server:app --port 7801
```

```bash
curl http://127.0.0.1:7801/health
# {"status":"ok","service":"asset_manager","version":"0.1.0"}
```

## Tests

```bash
pytest tests/ -v
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET  | /health | Liveness check |
| GET  | /catalog | List cataloged assets |
| POST | /select | Select an asset for a given request |
| POST | /generate | Dispatch AI generation |
| POST | /validate | Validate an asset on disk |
| POST | /bake | Commit a validated asset to the library |

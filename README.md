# Asset Manager — Library, Selector, Generator, AI Gateway

The sole writer of the asset library used by Forever engine. Catalogs every asset, selects the right one for a given context, generates new ones procedurally (creature tokens, item icons, terrain textures, tilesets), gateways to AI image models (Stable Diffusion / Scenario — stubs), validates AI-generated output before baking, and exposes everything over HTTP on port 7801.

**Spec:** `C:\Dev\.shared\docs\superpowers\specs\2026-04-06-three-module-consolidation-design.md`

## What this used to be

Before the 2026-04-06 three-module consolidation pivot, this directory was the legacy "Map Generator" — a Python pygame project plus 21 PCG agents. The pygame viewer has been archived to `C:\Dev\_archive\mapgen-pygame-viewer\`. The 21 PCG agents have been kept and moved to `asset_manager/generators/pcg/`.

## Status

**Phase 2 of the three-module pivot is complete + spec §14 follow-up #1 (C# → Python AssetGeneration port) is complete + bake CLI is shipped.** Asset Manager now has:

- A real asset library catalog (in-memory; SQLite/JSON-on-disk persistence is a follow-up).
- A real selector (currently always-misses; pattern matching is a follow-up).
- Four working procedural generators ported from C# in Round E:
  - `creature_token` — filled circle with rim
  - `item_icon` — square / circle / diamond shapes
  - `terrain` — Perlin-blended floor/wall textures
  - `tileset` — grids of single-color tiles with Perlin variation
- Two stub AI gateways (Stable Diffusion / Scenario — wired but not implemented; require API keys / local servers).
- A real validator composing the salvaged `border_detect` + `quality_metrics` from Gut It Out.
- A FastAPI bridge on port 7801 with `/health`, `/catalog`, `/select`, `/generate`, `/validate`, `/bake`.
- A headless `bake` CLI for recipe-driven offline content generation.
- A CI workflow that exercises pytest + uvicorn smoke test.
- A contract drift detector mirroring Director Hub's.

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

## Bake a batch of assets headlessly

```bash
python -m asset_manager.cli.bake asset_manager/cli/sample_recipe.yaml
```

The recipe YAML format is documented in `asset_manager/cli/bake.py`. Override the output root with `--root /tmp/test`.

## Generate one asset over HTTP

```bash
curl -X POST http://127.0.0.1:7801/generate \
  -H "Content-Type: application/json" \
  -d '{"schema_version":"1.0.0","kind":"creature_token","prompt":"goblin","constraints":{"color":[80,140,80,255],"size":32}}'
```

## Tests

```bash
pytest tests/ -v
```

The full suite covers the bridge, the four generators, the manifest builder, the bake CLI, the import smoke test (catches bare-import regressions), and the contract drift check. The 24 legacy `mapgen_agents`-era tests under `tests/legacy/` are quarantined via `conftest.py collect_ignore_glob`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET  | `/health` | Liveness check |
| GET  | `/catalog` | List cataloged assets |
| POST | `/select` | Select an asset for a given request |
| POST | `/generate` | Dispatch generation (creature_token / item_icon / terrain / tileset) |
| POST | `/validate` | Validate an asset on disk |
| POST | `/bake` | Register a generated asset in the catalog |

## Architecture

```
asset_manager/
├── library/
│   ├── catalog.py         In-memory catalog (Dict-backed)
│   ├── manifest.py        make_manifest helper
│   └── storage.py         path_for(kind, id, ext) under .shared/baked/
├── selectors/
│   ├── selector.py        Always-miss stub (real impl in follow-up)
│   └── rules.py           Match-by-kind/biome/theme helper
├── generators/
│   ├── _perlin.py         perlin-noise wrapper
│   ├── procedural_sprite.py    creature_token + item_icon (Pillow)
│   ├── texture.py              terrain + tileset (Pillow + Perlin)
│   ├── manifest_builder.py     Recursive directory scanner
│   ├── sprite_manager.py       Helper from the legacy Map Generator
│   └── pcg/                    21 mapgen agents (kept from the archive)
├── gateway/
│   ├── base.py            GenerationGateway ABC
│   ├── stable_diffusion.py  Stub
│   └── scenario.py        Stub
├── validators/
│   ├── border_detect/     Salvaged from Gut It Out (40-technique pipeline)
│   ├── quality_metrics.py Salvaged from Gut It Out
│   └── validator.py       Composes border_detect + alpha_stats with graceful degradation
├── exporters/
│   ├── unity_csharp.py    From the legacy Map Generator
│   ├── unity_scene.py
│   ├── unity_terrain.py
│   └── unity_tilemap.py
├── bridge/
│   ├── server.py          FastAPI app on port 7801
│   ├── schemas.py         Re-exports from _generated_schemas + local wrappers
│   └── _generated_schemas.py  Vendored from .shared/codegen/golden_python.py
├── cli/
│   ├── bake.py            Headless recipe-driven baking
│   └── sample_recipe.yaml 7-asset sample
└── shared_state.py        From the legacy Map Generator
```

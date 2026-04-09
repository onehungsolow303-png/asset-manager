# Asset Manager — Claude Code Project Rules

## What This Is
Python/FastAPI asset library, selector, and generator pipeline for the Forever engine RPG. Runs on port 7801. Manages the catalog of all visual assets (creature tokens, portraits, UI elements, 3D models), routes generation requests through a cost-aware deterministic protocol, and provides a browsable HTML index for visual review. Part of the four-repo ecosystem after the 2026-04-06 three-module consolidation pivot.

## Architecture
- **Library** (`library/`) — Catalog (JSON-backed), manifest schema (rich provenance), pack importer, seed pipeline, style bible, HTML index with thumbnails
- **Selectors** (`selectors/`) — Tag-overlap matching with biome/kind/theme scoring
- **Generators** (`generators/`) — Procedural sprites (Pillow), textures (Perlin), Blender headless renderer, local SD + LoRA stub
- **Gateway** (`gateway/`) — Cloud AI clients: Scenario.gg, Tripo3D, Nano Banana (Google Gemini 2.5 Flash Image). All env-var-gated.
- **Pipeline** (`pipeline/`) — Source-decision router (6-tier deterministic protocol), style audit (quality gate), LoRA trainer scaffolding
- **Bridge** (`bridge/server.py`) — FastAPI HTTP endpoints
- **CLI** (`cli/`) — 7 tools: inventory_packs, extract_packs, bulk_import, curate_lora_dataset, ship_export_check, watch_move, regen_licenses

## Repo Ecosystem
- **Forever engine** (`C:\Dev\Forever engine`) — Unity 6 game runtime (the client)
- **Director Hub** (`C:\Dev\Director Hub`) — Agentic AI brain
- **Asset Manager** (`C:\Dev\Asset Manager`) — This repo. Asset library + pipeline.
- **`.shared`** (`C:\Dev\.shared`) — Cross-module contracts, schemas, codegen

## Rules

1. **Asset Manager is the only writer of the asset library.** The catalog at `.shared/state/asset_catalog.json` is the single source of truth. Forever engine reads via HTTP `/select`; never writes directly.
2. **Every manifest entry must have provenance.** `source` (pack/procedural/ai_2d/ai_3d/blender/unknown), `license`, `cost_usd`, `redistribution`, `swap_safe`. The deterministic protocol and ship_export_check depend on these fields.
3. **Catalog prunes on startup.** `Catalog.__init__` calls `prune_missing_files()` to remove entries whose path no longer exists on disk. Don't rely on catalog entries being permanent — the file must exist.
4. **Catalog always loads from disk** regardless of `persist` flag. `persist` controls WRITES, not READS. The ship_export_check CLI relies on this (persist=False for read-only audit).
5. **The deterministic protocol routes by cost.** cache → library → procedural → local_sd_lora → nano_banana → tripo3d. Free tiers always tried first. Paid tiers gated by per-session budget ceiling (default $1.00).
6. **Ship export check is the license gate.** `redistribution=false` assets are playtest-only. Run `python -m asset_manager.cli.ship_export_check` before any commercial build. Currently 13,676 Roll20 marketplace assets flagged as must-replace.
7. **Style bible is the art direction source of truth.** Every generator reads the style bible before producing an asset. Edit `.shared/state/style_bible.json` to change the art direction globally.
8. **HTML index auto-refreshes.** Every catalog mutation triggers `_refresh_html_index()` which regenerates `.shared/baked/index.html` with thumbnails. The index uses JSON-embedded data + JS pagination for 13k+ scale performance.
9. **Thumbnails are idempotent.** `html_index_thumbs.py` skips regeneration when the thumb mtime >= source mtime. Force regeneration by deleting the thumbs/ directory.
10. **Pack imports are idempotent.** Re-running `/import_pack` with the same asset_id_prefix updates existing entries in place. generated_at is preserved across re-imports.

## HTTP Endpoints (port 7801)
- `GET /health` — liveness check
- `GET /catalog` — list all catalog entries
- `POST /select` — find best-matching asset by kind + biome + tags
- `POST /generate` — procedural asset generation
- `POST /bake` — register a pre-existing asset
- `POST /validate` — validate an asset path (stub)
- `POST /import_pack` — import a third-party asset pack
- `GET /style_bible` — read the full style bible
- `GET /style_bible/category/{kind}` — effective rules for one asset kind
- `POST /audit` — run style/quality audit on an asset
- `GET /router_status` — generation tier availability + costs

## Environment Variables (all optional — gateways are dormant without them)
- `TRIPO_API_KEY` — activates Tripo3D gateway (image-to-3D)
- `GEMINI_API_KEY` — activates Nano Banana gateway (image-to-image editing)
- `BLENDER_EXECUTABLE` — activates Blender headless renderer
- `DIRECTOR_HUB_REPLAY_MODE` — record/replay for golden tests (Director Hub, not AM)

## Testing
```bash
cd "C:/Dev/Asset Manager"
.venv/Scripts/python.exe -m pytest tests/ -q
# 325 tests, ~15 seconds
```

## Key Files
- `library/catalog.py` — disk-backed catalog with prune + migrate + auto-scan
- `library/manifest.py` — provenance schema (make_manifest + migrate_manifest)
- `library/pack_importer.py` — third-party pack import with collision-safe prefixes
- `library/style_bible.py` — JSON-backed art direction
- `library/html_index.py` — paginated catalog browser (JSON-embedded + JS)
- `library/html_index_thumbs.py` — Pillow thumbnail renderer
- `pipeline/source_decision.py` — 6-tier deterministic routing
- `pipeline/style_audit.py` — quality gate before catalog registration
- `gateway/tripo3d.py` — Tripo3D API client
- `gateway/nano_banana.py` — Google Gemini 2.5 Flash Image client
- `bridge/server.py` — FastAPI app with all endpoints

## Catalog State
- **Location:** `.shared/state/asset_catalog.json`
- **Current entries:** 13,800+ (mostly Roll20 Forgotten Adventures tokens)
- **HTML index:** `.shared/baked/index.html` (6 MB, paginated, searchable)
- **Thumbnails:** `.shared/baked/thumbs/` (256 MB, 13,800+ files)
- **LoRA dataset:** `.shared/lora_training/dnd_style_v1/source/` (575 MB, 300 curated images)

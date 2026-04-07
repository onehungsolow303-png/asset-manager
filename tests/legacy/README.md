# Legacy tests — quarantined 2026-04-06

These 24 pytest files were written against the pre-pivot `mapgen_agents.*` flat layout. After the three-module consolidation pivot moved everything to `asset_manager/generators/pcg/`, their imports no longer resolve. They are kept here for reference (some will be revivable as `asset_manager/generators/pcg/` tests with import-path edits, others test the archived pygame viewer and should stay archived).

`tests/conftest.py` skips this directory by default via `collect_ignore_glob = ["legacy/*"]`. Running them deliberately:

```bash
pytest tests/legacy/  # will fail at collection until imports are fixed
```

## What's here

- `test_cave_carver.py`, `test_terrain_enhanced.py`, `test_structure_enhanced.py`, `test_topology_agent.py`, `test_pathfinding_enhanced.py`, `test_zlevel.py`, `test_room_graph.py`, `test_room_purpose_agent.py`, `test_room_purposes.py`, `test_connector_agent.py`, `test_dressing_agent.py`, `test_spawn_agent.py`, `test_encounter_agent.py`, `test_loot_agent.py`, `test_trap_agent.py`, `test_game_tables.py` — PCG agent tests. Revivable: rewrite the imports to `from asset_manager.generators.pcg.X import Y`.
- `test_pipeline_coordinator.py`, `test_phase2_integration.py`, `test_phase3_integration.py`, `test_profiles.py`, `test_validation.py`, `test_generation_request.py` — PCG pipeline tests. Same fix applies.
- `test_combat.py`, `test_viewer_loader.py` — pygame viewer tests. The viewer is archived to `C:\Dev\_archive\mapgen-pygame-viewer\`. Discard or move to that archive.

"""End-to-end smoke tests for the Asset Manager HTTP endpoints.

Locks in the procedural-only behavior of /generate, /select, /catalog,
and /bake against the seeded library state. These are the regression
guards for the seed pipeline (creature_token + item_icon) and the
catalog prune-on-load mechanism.

Why these aren't in test_bridge.py:
  test_bridge.py covers individual endpoint shapes in isolation
  (status codes, schema fields). This file covers cross-endpoint
  flows: "after seed runs, can I select what was seeded?", "does
  generate then catalog round-trip?", etc. They share the same
  TestClient fixture from conftest.py.
"""

from __future__ import annotations

# ─── Catalog seed visibility ───────────────────────────────────────


def test_catalog_includes_seeded_creature_tokens(client):
    """At Asset Manager startup, seed_default_creature_tokens populates
    the library with the canonical 16 creature tokens. The /catalog
    endpoint should expose at least the well-known ones."""
    r = client.get("/catalog")
    assert r.status_code == 200
    body = r.json()
    asset_ids = {a.get("asset_id") for a in body["assets"]}
    # Spot-check a handful from different biomes; the full list lives
    # in seed.py:_SEED_CREATURES and may grow over time.
    for expected in ("wolf", "bandit", "skeleton", "the_rot_king"):
        assert expected in asset_ids, f"missing seeded creature token: {expected}"


def test_catalog_includes_seeded_item_icons(client):
    """seed_default_item_icons populates Food/Water/HealthPotion icons
    matching Forever engine's PlayerData ItemIds (100/101/102). They
    must show up in the catalog after Asset Manager startup."""
    r = client.get("/catalog")
    assert r.status_code == 200
    body = r.json()
    asset_ids = {a.get("asset_id") for a in body["assets"]}
    for expected in ("food", "water", "health_potion"):
        assert expected in asset_ids, f"missing seeded item icon: {expected}"


# ─── Select for seeded assets ──────────────────────────────────────


def test_select_creature_token_by_tag_hits_seed(client):
    """Forever engine's BattleManager.RequestEnemySprites issues a
    /select with kind=creature_token + biome + tags=[name.lower()].
    Verify the seeded wolf hits."""
    payload = {
        "schema_version": "1.0.0",
        "kind": "creature_token",
        "biome": "forest",
        "tags": ["wolf"],
        "allow_ai_generation": False,
    }
    r = client.post("/select", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert body["asset_id"] == "wolf"
    # Path must point at the real baked PNG
    assert body["path"].endswith("wolf.png")
    # Manifest must echo the kind so callers can route by it
    assert body["manifest"]["kind"] == "creature_token"


def test_select_item_icon_by_tag_hits_seed(client):
    """Same flow as creature tokens, but for the new item icon seed.
    A future inventory UI calling /select?kind=item_icon&tags=[health_potion]
    should get a hit instead of falling through to the procedural fallback."""
    payload = {
        "schema_version": "1.0.0",
        "kind": "item_icon",
        "tags": ["health_potion"],
        "allow_ai_generation": False,
    }
    r = client.post("/select", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert body["asset_id"] == "health_potion"
    assert body["path"].endswith("health_potion.png")
    assert body["manifest"]["kind"] == "item_icon"


def test_select_unknown_kind_returns_miss(client):
    """An unknown asset kind must return found=False — the selector's
    `kind` matcher is strict (exact match). Selector regression guard:
    a future change loosening kind matching would silently route the
    wrong assets to wrong consumers, which is hard to spot in
    production. Locking strict-kind here.

    Note: we use an unknown KIND rather than an unknown tag for the
    miss case because the matcher is intentionally tolerant about
    tags — a no-tag fallback asset (e.g. an untagged creature_token
    from a manual /bake call) will satisfy any tag query. That's the
    design, not a bug."""
    payload = {
        "schema_version": "1.0.0",
        "kind": "phaser_blast",  # not a real kind
        "tags": ["pew"],
        "allow_ai_generation": False,
    }
    r = client.post("/select", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is False


# ─── Procedural generate round-trip ────────────────────────────────


def test_generate_creature_token_round_trips_to_catalog(client):
    """POST /generate with kind=creature_token must produce a real PNG
    on disk AND register the asset in the catalog so a follow-up
    /catalog call can see it. Procedural path: the bridge always uses
    the procedural generator regardless of prompt, so prompt content
    is just metadata for the catalog manifest."""
    gen_payload = {
        "schema_version": "1.0.0",
        "kind": "creature_token",
        "prompt": "a smoke-test creature with red color",
        "constraints": {"color": [200, 50, 50, 255], "size": 32},
    }
    gen = client.post("/generate", json=gen_payload)
    assert gen.status_code == 200
    gen_body = gen.json()
    assert gen_body["accepted"] is True
    new_id = gen_body.get("asset_id")
    assert new_id and new_id.startswith("token_")

    # The newly-generated asset must show up in /catalog
    cat = client.get("/catalog")
    asset_ids = {a.get("asset_id") for a in cat.json()["assets"]}
    assert new_id in asset_ids


def test_generate_item_icon_round_trips_to_catalog(client):
    """Same round-trip check for the item_icon procedural generator."""
    gen_payload = {
        "schema_version": "1.0.0",
        "kind": "item_icon",
        "prompt": "a smoke-test green circle item",
        "constraints": {"color": [80, 200, 80, 255], "shape": "circle", "size": 16},
    }
    gen = client.post("/generate", json=gen_payload)
    assert gen.status_code == 200
    gen_body = gen.json()
    assert gen_body["accepted"] is True
    new_id = gen_body.get("asset_id")
    assert new_id and new_id.startswith("icon_")

    cat = client.get("/catalog")
    asset_ids = {a.get("asset_id") for a in cat.json()["assets"]}
    assert new_id in asset_ids


# ─── Catalog prune ─────────────────────────────────────────────────


def test_catalog_prune_removes_missing_files(tmp_path):
    """Direct unit test of Catalog.prune_missing_files — bypasses the
    HTTP layer so we can construct a catalog with known-bad entries
    and verify they're swept. The startup flow exercised through the
    TestClient fixture above also runs prune_on_load=True; this test
    pins the contract for the underlying mechanism."""
    from asset_manager.library.catalog import Catalog

    # Build a catalog with one real file and one missing file
    real_file = tmp_path / "real.png"
    real_file.write_bytes(b"\x89PNG\r\n\x1a\n")  # 8-byte PNG header
    missing_file = tmp_path / "ghost.png"  # never created

    cat_path = tmp_path / "catalog.json"
    catalog = Catalog(
        path=cat_path,
        persist=True,
        auto_scan_baked=False,
        prune_on_load=False,
    )
    catalog.add("real_asset", {"kind": "test", "path": str(real_file)})
    catalog.add("ghost_asset", {"kind": "test", "path": str(missing_file)})

    assert catalog.count() == 2

    pruned = catalog.prune_missing_files()
    assert pruned == 1
    assert catalog.get("real_asset") is not None
    assert catalog.get("ghost_asset") is None
    assert catalog.count() == 1


def test_catalog_prune_handles_entries_without_path(tmp_path):
    """Catalog entries without a `path` field (partial manifests under
    construction) must NOT be pruned — only entries with an explicit
    missing path. This protects against eating in-flight bake jobs."""
    from asset_manager.library.catalog import Catalog

    cat_path = tmp_path / "catalog.json"
    catalog = Catalog(
        path=cat_path,
        persist=True,
        auto_scan_baked=False,
        prune_on_load=False,
    )
    catalog.add("pending", {"kind": "test"})  # no `path` key
    assert catalog.count() == 1

    pruned = catalog.prune_missing_files()
    assert pruned == 0
    assert catalog.get("pending") is not None

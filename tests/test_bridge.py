def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "asset_manager"


def test_catalog_returns_empty_initially(client):
    r = client.get("/catalog")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["assets"] == []


def test_select_returns_miss_in_stub(client):
    payload = {
        "schema_version": "1.0.0",
        "kind": "sprite",
        "biome": "swamp",
        "theme": "overgrown",
        "tags": ["wall"],
        "allow_ai_generation": False,
    }
    r = client.post("/select", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is False
    assert "miss" in body["notes"][0]


def test_generate_unknown_kind_returns_not_accepted(client):
    payload = {
        "schema_version": "1.0.0",
        "kind": "phaser_blast",
        "prompt": "stun the enemy",
    }
    r = client.post("/generate", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is False
    assert "unknown kind" in body["notes"][0]


def test_validate_requires_path(client):
    r = client.post("/validate", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] is False
    assert "missing 'path'" in body["notes"][0]


def test_select_rejects_missing_kind(client):
    bad = {"schema_version": "1.0.0", "biome": "forest"}
    r = client.post("/select", json=bad)
    assert r.status_code == 422


def test_generate_creature_token_writes_real_png(client, tmp_path, monkeypatch):
    """Generate a creature token and verify the PNG is on disk."""
    # Redirect Storage to a tmp dir so we don't pollute .shared/baked
    from pathlib import Path

    from PIL import Image

    from asset_manager.bridge import server
    from asset_manager.library.storage import Storage

    monkeypatch.setattr(server, "_storage", Storage(root=tmp_path))

    payload = {
        "schema_version": "1.0.0",
        "kind": "creature_token",
        "prompt": "fierce wolf",
        "constraints": {"color": [200, 50, 50, 255], "size": 32},
    }
    r = client.post("/generate", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is True
    assert body["asset_id"].startswith("token_")
    assert body["path"].endswith(".png")

    out = Path(body["path"])
    assert out.exists()
    img = Image.open(out)
    assert img.size == (32, 32)
    assert img.mode == "RGBA"


def test_bake_registers_in_catalog(client):
    r = client.post(
        "/bake",
        json={
            "asset_id": "token_test123",
            "kind": "creature_token",
            "path": "/tmp/fake.png",
        },
    )
    assert r.status_code == 200
    assert r.json()["baked"] is True

    cat = client.get("/catalog").json()
    assert any(a.get("asset_id") == "token_test123" for a in cat["assets"])

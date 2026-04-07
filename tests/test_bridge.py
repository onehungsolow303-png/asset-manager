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


def test_generate_returns_not_implemented(client):
    payload = {
        "schema_version": "1.0.0",
        "kind": "sprite",
        "prompt": "scorched loot variant",
    }
    r = client.post("/generate", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is False
    assert "stub" in body["notes"][0].lower()


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

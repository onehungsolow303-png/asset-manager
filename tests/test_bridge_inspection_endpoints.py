"""HTTP tests for the new safe inspection endpoints.

These all share the existing `client` fixture from conftest.py and
verify the four read-only endpoints added in the asset pipeline batch:

  GET  /style_bible
  GET  /style_bible/category/{kind}
  POST /audit
  GET  /router_status

None of them mutate state. None of them call paid APIs. They expose
the inspection surface so the user can verify the system from `curl`
without booting the Python REPL.
"""

from __future__ import annotations

from pathlib import Path


def test_get_style_bible_returns_full_dict(client):
    r = client.get("/style_bible")
    assert r.status_code == 200
    body = r.json()
    assert "art_style" in body
    assert "color_palette" in body
    # The default art_style mentions D&D
    assert "D&D" in body["art_style"]


def test_get_style_bible_category_returns_merged_rules(client):
    r = client.get("/style_bible/category/creature_token")
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "creature_token"
    assert "rules" in body
    assert "prompt_preamble" in body
    # Override-specific perspective should win
    assert "top-down" in body["rules"]["perspective"]


def test_get_style_bible_category_for_unknown_kind_returns_globals(client):
    r = client.get("/style_bible/category/totally_made_up")
    assert r.status_code == 200
    body = r.json()
    # Falls through to globals when no override exists
    assert "rules" in body
    assert body["rules"]["art_style"] is not None


# ─── /audit ──────────────────────────────────────────────────────────


def test_audit_endpoint_passes_for_valid_png(client, tmp_path):
    from PIL import Image

    p = tmp_path / "test.png"
    Image.new("RGBA", (32, 32), (200, 100, 50, 255)).save(p)

    r = client.post(
        "/audit",
        json={
            "asset_id": "test_wolf",
            "kind": "creature_token",
            "path": str(p),
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] is True
    assert body["asset_id"] == "test_wolf"
    assert body["failures"] == []


def test_audit_endpoint_fails_on_missing_file(client, tmp_path):
    r = client.post(
        "/audit",
        json={
            "asset_id": "ghost",
            "kind": "creature_token",
            "path": str(tmp_path / "ghost.png"),
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] is False
    assert any("does not exist" in f for f in body["failures"])


def test_audit_endpoint_validates_required_fields(client):
    r = client.post("/audit", json={"asset_id": "wolf"})  # missing kind, path
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] is False
    assert any("missing required" in f for f in body["failures"])


# ─── /router_status ──────────────────────────────────────────────────


def test_router_status_lists_all_tiers(client):
    r = client.get("/router_status")
    assert r.status_code == 200
    body = r.json()
    assert "tiers" in body

    tier_names = {t["name"] for t in body["tiers"]}
    # All 7 tiers (cache + library + procedural + blender + local_sd + nano + tripo)
    assert "cache" in tier_names
    assert "library" in tier_names
    assert "procedural" in tier_names
    assert "blender_renderer" in tier_names
    assert "local_sd_lora" in tier_names
    assert "nano_banana" in tier_names
    assert "tripo3d" in tier_names


def test_router_status_tier_costs_present(client):
    r = client.get("/router_status")
    body = r.json()
    for tier in body["tiers"]:
        assert "cost_per_call_usd" in tier
        assert "available" in tier
        assert "notes" in tier
        assert tier["cost_per_call_usd"] >= 0.0


def test_router_status_marks_paid_tiers_unavailable_without_keys(client, monkeypatch):
    """Without TRIPO_API_KEY / GEMINI_API_KEY set, the paid tiers
    should report available=False."""
    monkeypatch.delenv("TRIPO_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    r = client.get("/router_status")
    body = r.json()
    by_name = {t["name"]: t for t in body["tiers"]}

    # Paid cloud tiers should be unavailable without keys
    assert by_name["tripo3d"]["available"] is False
    assert by_name["nano_banana"]["available"] is False
    # Free cache/library/procedural tiers always available
    assert by_name["cache"]["available"] is True
    assert by_name["library"]["available"] is True
    assert by_name["procedural"]["available"] is True

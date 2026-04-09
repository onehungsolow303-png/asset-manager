"""Tests for the ship_export_check CLI."""
from __future__ import annotations

import json
from pathlib import Path

from asset_manager.cli.ship_export_check import (
    find_must_replace,
    summarize,
    write_csv_report,
)
from asset_manager.library.catalog import Catalog
from asset_manager.library.manifest import make_manifest


def _make_catalog(tmp_path, entries: list[dict]) -> Catalog:
    """Build a real Catalog instance with the given entries."""
    catalog_path = tmp_path / "catalog.json"
    catalog = Catalog(
        path=catalog_path, persist=True,
        auto_scan_baked=False, prune_on_load=False,
    )
    for entry in entries:
        catalog.add(entry["asset_id"], entry)
    return catalog


# ─── find_must_replace ────────────────────────────────────────────

def test_find_returns_only_redistribution_false(tmp_path):
    catalog = _make_catalog(tmp_path, [
        make_manifest(asset_id="ok", kind="creature_token", path="/x/ok.png",
                       redistribution=True),
        make_manifest(asset_id="bad1", kind="creature_token", path="/x/bad1.png",
                       redistribution=False, license="Roll20_marketplace_personal"),
        make_manifest(asset_id="bad2", kind="portrait", path="/x/bad2.png",
                       redistribution=False, license="Synty_standard"),
    ])

    must_replace = find_must_replace(catalog)
    asset_ids = {a["asset_id"] for a in must_replace}
    assert "ok" not in asset_ids
    assert "bad1" in asset_ids
    assert "bad2" in asset_ids


def test_find_treats_missing_redistribution_as_safe(tmp_path):
    """Catalog entries without an explicit redistribution field default
    to True (safe). They should NOT be flagged as must-replace."""
    catalog = _make_catalog(tmp_path, [
        {"asset_id": "legacy", "kind": "creature_token", "path": "/x/legacy.png"},
    ])
    must_replace = find_must_replace(catalog)
    assert must_replace == []


def test_find_returns_empty_when_clean(tmp_path):
    catalog = _make_catalog(tmp_path, [
        make_manifest(asset_id="ok1", kind="creature_token", path="/x/ok1.png", redistribution=True),
        make_manifest(asset_id="ok2", kind="portrait", path="/x/ok2.png", redistribution=True),
    ])
    assert find_must_replace(catalog) == []


# ─── summarize ────────────────────────────────────────────────────

def test_summarize_groups_by_license_pack_kind_source():
    must_replace = [
        {"asset_id": "a", "kind": "portrait", "source": "pack",
         "license": "Roll20_marketplace_personal", "pack_name": "Roll20 Pack 1"},
        {"asset_id": "b", "kind": "portrait", "source": "pack",
         "license": "Roll20_marketplace_personal", "pack_name": "Roll20 Pack 1"},
        {"asset_id": "c", "kind": "building", "source": "pack",
         "license": "Synty_standard", "pack_name": "Synty Pack"},
    ]
    s = summarize(must_replace)
    assert s["total"] == 3
    assert s["by_license"]["Roll20_marketplace_personal"] == 2
    assert s["by_license"]["Synty_standard"] == 1
    assert s["by_pack"]["Roll20 Pack 1"] == 2
    assert s["by_pack"]["Synty Pack"] == 1
    assert s["by_kind"]["portrait"] == 2
    assert s["by_kind"]["building"] == 1
    assert s["by_source"]["pack"] == 3


def test_summarize_handles_empty():
    s = summarize([])
    assert s["total"] == 0
    assert s["by_license"] == {}


def test_summarize_handles_missing_pack_name():
    """Entries with no pack_name should be grouped under '(no pack)'."""
    must_replace = [
        {"asset_id": "a", "kind": "x", "source": "x", "license": "x"},  # no pack_name
    ]
    s = summarize(must_replace)
    assert s["by_pack"]["(no pack)"] == 1


# ─── CSV output ────────────────────────────────────────────────────

def test_write_csv_report_creates_file_with_expected_columns(tmp_path):
    must_replace = [
        {
            "asset_id": "wolf", "kind": "creature_token", "source": "pack",
            "pack_name": "Roll20 Pack", "license": "Roll20_marketplace_personal",
            "cost_usd": 0.0, "path": "/x/wolf.png",
            "tags": ["wolf", "forest"], "biome": "forest",
            "generated_at": "2026-04-08T20:00:00+00:00",
        },
    ]
    out = tmp_path / "report.csv"
    write_csv_report(must_replace, out)

    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "asset_id" in content  # header
    assert "wolf" in content
    assert "Roll20 Pack" in content
    assert "wolf,forest" in content  # tags joined
    assert "forest" in content


def test_write_csv_handles_empty_list(tmp_path):
    out = tmp_path / "empty.csv"
    write_csv_report([], out)
    assert out.exists()
    # Just the header
    lines = out.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    assert "asset_id" in lines[0]


def test_write_csv_creates_parent_directory(tmp_path):
    out = tmp_path / "deep" / "nested" / "report.csv"
    write_csv_report([], out)
    assert out.exists()

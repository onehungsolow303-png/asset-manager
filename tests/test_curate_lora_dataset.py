"""Tests for the curate_lora_dataset CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from asset_manager.cli.curate_lora_dataset import (
    copy_to_dataset,
    filter_assets,
    round_robin_select,
    write_manifest,
)
from asset_manager.library.catalog import Catalog
from asset_manager.library.manifest import make_manifest


def _make_catalog(tmp_path, entries: list[dict]) -> Catalog:
    cat_path = tmp_path / "catalog.json"
    cat = Catalog(path=cat_path, persist=True, auto_scan_baked=False, prune_on_load=False)
    for e in entries:
        cat.add(e["asset_id"], e)
    return cat


def _png(tmp_path: Path, name: str) -> str:
    """Write a tiny PNG and return its path string."""
    from PIL import Image

    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), (200, 100, 50)).save(p, format="PNG")
    return str(p)


# ─── filter_assets ─────────────────────────────────────────────────


def test_filter_drops_non_image_paths(tmp_path):
    cat = _make_catalog(
        tmp_path,
        [
            make_manifest(asset_id="img", kind="portrait", path=_png(tmp_path, "a.png")),
            make_manifest(asset_id="mesh", kind="character", path=str(tmp_path / "b.glb")),
        ],
    )
    pool = filter_assets(cat)
    ids = {a["asset_id"] for a in pool}
    assert "img" in ids
    assert "mesh" not in ids


def test_filter_by_kind(tmp_path):
    cat = _make_catalog(
        tmp_path,
        [
            make_manifest(asset_id="a", kind="portrait", path=_png(tmp_path, "a.png")),
            make_manifest(asset_id="b", kind="creature_token", path=_png(tmp_path, "b.png")),
        ],
    )
    pool = filter_assets(cat, kind="portrait")
    assert {a["asset_id"] for a in pool} == {"a"}


def test_filter_by_source(tmp_path):
    cat = _make_catalog(
        tmp_path,
        [
            make_manifest(
                asset_id="a", kind="portrait", path=_png(tmp_path, "a.png"), source="pack"
            ),
            make_manifest(
                asset_id="b", kind="portrait", path=_png(tmp_path, "b.png"), source="procedural"
            ),
        ],
    )
    pool = filter_assets(cat, source="pack")
    assert {a["asset_id"] for a in pool} == {"a"}


def test_filter_by_pack_pattern_case_insensitive(tmp_path):
    cat = _make_catalog(
        tmp_path,
        [
            make_manifest(
                asset_id="a",
                kind="portrait",
                path=_png(tmp_path, "a.png"),
                pack_name="FA Tokens Adventurers",
            ),
            make_manifest(
                asset_id="b",
                kind="portrait",
                path=_png(tmp_path, "b.png"),
                pack_name="Roll20 D&D Originals",
            ),
        ],
    )
    pool = filter_assets(cat, pack_patterns=["fa tokens"])
    assert {a["asset_id"] for a in pool} == {"a"}


def test_filter_drops_paths_without_path_field(tmp_path):
    cat_path = tmp_path / "catalog.json"
    cat = Catalog(path=cat_path, persist=True, auto_scan_baked=False, prune_on_load=False)
    cat.add("a", {"asset_id": "a", "kind": "portrait", "path": _png(tmp_path, "a.png")})
    cat.add("orphan", {"asset_id": "orphan", "kind": "portrait"})  # no path
    pool = filter_assets(cat)
    assert {a["asset_id"] for a in pool} == {"a"}


# ─── round_robin_select ────────────────────────────────────────────


def test_round_robin_picks_target_count():
    assets = [{"asset_id": f"a{i}", "pack_name": "PackA"} for i in range(10)] + [
        {"asset_id": f"b{i}", "pack_name": "PackB"} for i in range(10)
    ]
    selected = round_robin_select(assets, target_count=8, max_per_pack=10)
    assert len(selected) == 8


def test_round_robin_alternates_packs():
    """With 5 from PackA and 5 from PackB, the selection should
    interleave them rather than taking all 5 from one pack first."""
    assets = [{"asset_id": f"a{i}", "pack_name": "PackA"} for i in range(5)] + [
        {"asset_id": f"b{i}", "pack_name": "PackB"} for i in range(5)
    ]
    selected = round_robin_select(assets, target_count=10, max_per_pack=10)
    # First two should be one A and one B (sorted alphabetically: PackA first)
    assert selected[0]["pack_name"] == "PackA"
    assert selected[1]["pack_name"] == "PackB"
    # And alternate from there
    a_count = sum(1 for s in selected if s["pack_name"] == "PackA")
    b_count = sum(1 for s in selected if s["pack_name"] == "PackB")
    assert a_count == 5 and b_count == 5


def test_round_robin_caps_per_pack():
    """One pack with 100 assets, another with 5. Cap per pack=10
    means we get 10 from the big pack and all 5 from the small one."""
    assets = [{"asset_id": f"big{i}", "pack_name": "Big"} for i in range(100)] + [
        {"asset_id": f"small{i}", "pack_name": "Small"} for i in range(5)
    ]
    selected = round_robin_select(assets, target_count=200, max_per_pack=10)
    big = sum(1 for s in selected if s["pack_name"] == "Big")
    small = sum(1 for s in selected if s["pack_name"] == "Small")
    assert big == 10
    assert small == 5
    assert len(selected) == 15


def test_round_robin_handles_empty():
    assert round_robin_select([], 10, 5) == []


def test_round_robin_zero_target():
    assets = [{"asset_id": "a", "pack_name": "P"}]
    assert round_robin_select(assets, 0, 5) == []


def test_round_robin_deterministic_within_pack():
    """Two runs with the same input must produce the same selection."""
    assets = [{"asset_id": f"x{i}", "pack_name": "P"} for i in range(20)]
    a = round_robin_select(assets, 5, 10)
    b = round_robin_select(assets, 5, 10)
    assert [s["asset_id"] for s in a] == [s["asset_id"] for s in b]


def test_round_robin_groups_unnamed_packs():
    """Assets without a pack_name fall into the '(no pack)' bucket."""
    assets = [
        {"asset_id": "a", "pack_name": None},
        {"asset_id": "b"},
    ]
    selected = round_robin_select(assets, 2, 5)
    assert len(selected) == 2


# ─── copy_to_dataset ───────────────────────────────────────────────


def test_copy_to_dataset_copies_files(tmp_path):
    src1 = _png(tmp_path / "src", "wolf.png")
    src2 = _png(tmp_path / "src", "bear.png")
    selected = [
        {"asset_id": "wolf", "path": src1},
        {"asset_id": "bear", "path": src2},
    ]
    target = tmp_path / "dataset"
    copied, skipped = copy_to_dataset(selected, target)
    assert copied == 2
    assert skipped == 0
    assert (target / "wolf.png").exists()
    assert (target / "bear.png").exists()


def test_copy_to_dataset_skips_missing(tmp_path):
    real = _png(tmp_path / "src", "wolf.png")
    selected = [
        {"asset_id": "wolf", "path": real},
        {"asset_id": "ghost", "path": str(tmp_path / "ghost.png")},
    ]
    copied, skipped = copy_to_dataset(selected, tmp_path / "dataset")
    assert copied == 1
    assert skipped == 1


def test_copy_to_dataset_idempotent(tmp_path):
    src = _png(tmp_path / "src", "wolf.png")
    selected = [{"asset_id": "wolf", "path": src}]
    target = tmp_path / "dataset"
    copy_to_dataset(selected, target)
    copied, skipped = copy_to_dataset(selected, target)
    # Already-present file is counted as copied (no error)
    assert copied == 1
    assert skipped == 0


# ─── write_manifest ────────────────────────────────────────────────


def test_write_manifest_outputs_csv(tmp_path):
    selected = [
        {
            "asset_id": "wolf",
            "kind": "creature_token",
            "source": "pack",
            "pack_name": "Test",
            "license": "CC0",
            "path": "/x/wolf.png",
            "tags": ["wolf", "forest"],
        },
    ]
    out = tmp_path / "manifest.csv"
    write_manifest(selected, out)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "asset_id" in content
    assert "wolf" in content
    assert "wolf,forest" in content

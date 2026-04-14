"""Catalog persistence + selector matching tests."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from asset_manager.library.catalog import Catalog
from asset_manager.selectors.rules import matches, score
from asset_manager.selectors.selector import Selector


def _img(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(path)


# ---------------------------------------------------------------- Catalog


def test_catalog_persists_across_instances(tmp_path: Path):
    cat_path = tmp_path / "catalog.json"
    first = Catalog(path=cat_path, persist=True, auto_scan_baked=False)
    first.add("a1", {"kind": "sprite", "biome": "forest"})
    first.add("a2", {"kind": "tileset"})
    assert first.count() == 2

    # Simulate restart
    second = Catalog(path=cat_path, persist=True, auto_scan_baked=False)
    assert second.count() == 2
    assert second.get("a1")["biome"] == "forest"


def test_catalog_in_memory_only(tmp_path: Path):
    cat_path = tmp_path / "catalog.json"
    cat = Catalog(path=cat_path, persist=False, auto_scan_baked=False)
    cat.add("a1", {"kind": "sprite"})
    assert not cat_path.exists()


def test_catalog_remove_and_wipe(tmp_path: Path):
    cat = Catalog(path=tmp_path / "c.json", persist=True, auto_scan_baked=False)
    cat.add("a", {"kind": "sprite"})
    cat.add("b", {"kind": "tileset"})
    assert cat.remove("a") is True
    assert cat.count() == 1
    assert cat.remove("nonexistent") is False
    cat.wipe()
    assert cat.count() == 0
    assert not (tmp_path / "c.json").exists()


def test_catalog_auto_scan_baked(tmp_path: Path):
    baked = tmp_path / "baked"
    _img(baked / "creature_token" / "wolf.png")
    _img(baked / "creature_token" / "goblin.png")
    _img(baked / "tileset" / "grass.png")
    _img(baked / "loose_at_root.png")  # 1 directory deep, ignored

    cat = Catalog(
        path=tmp_path / "c.json",
        persist=True,
        auto_scan_baked=True,
        baked_root=baked,
    )
    assert cat.count() == 3
    wolf = cat.get("wolf")
    assert wolf is not None
    assert wolf["kind"] == "creature_token"
    assert wolf["path"].endswith("wolf.png")


def test_catalog_auto_scan_does_not_clobber_existing(tmp_path: Path):
    baked = tmp_path / "baked"
    _img(baked / "creature_token" / "wolf.png")

    cat_path = tmp_path / "c.json"
    first = Catalog(
        path=cat_path,
        persist=True,
        auto_scan_baked=False,
    )
    first.add("wolf", {"kind": "sprite", "biome": "tundra", "manual": True})

    second = Catalog(
        path=cat_path,
        persist=True,
        auto_scan_baked=True,
        baked_root=baked,
    )
    wolf = second.get("wolf")
    assert wolf["manual"] is True  # not overwritten
    assert wolf["biome"] == "tundra"


# ---------------------------------------------------------------- rules


def test_matches_kind():
    assert matches({"kind": "sprite"}, {"kind": "sprite"}) is True
    assert matches({"kind": "sprite"}, {"kind": "tileset"}) is False


def test_matches_tags_overlap():
    asset = {"kind": "sprite", "tags": ["wall", "stone"]}
    assert matches(asset, {"kind": "sprite", "tags": ["wall"]}) is True
    assert matches(asset, {"kind": "sprite", "tags": ["wall", "ice"]}) is True
    assert matches(asset, {"kind": "sprite", "tags": ["water"]}) is False


def test_matches_tolerates_missing_biome_on_asset():
    """Assets without a biome are 'generic' and match any biome request."""
    assert matches({"kind": "sprite"}, {"kind": "sprite", "biome": "forest"}) is True


def test_score_higher_when_more_fields_align():
    asset = {"kind": "sprite", "biome": "forest", "tags": ["wall"]}
    base = {"kind": "sprite"}
    biome_match = {"kind": "sprite", "biome": "forest"}
    tag_match = {"kind": "sprite", "biome": "forest", "tags": ["wall"]}
    assert score(asset, base) < score(asset, biome_match) < score(asset, tag_match)


# ---------------------------------------------------------------- Selector


def test_selector_returns_none_on_empty_catalog(tmp_path: Path):
    cat = Catalog(path=tmp_path / "c.json", persist=False, auto_scan_baked=False)
    sel = Selector(cat)
    assert sel.select({"kind": "sprite"}) is None


def test_selector_picks_best_match(tmp_path: Path):
    cat = Catalog(path=tmp_path / "c.json", persist=False, auto_scan_baked=False)
    cat.add("plain_wall", {"kind": "sprite", "tags": ["wall"]})
    cat.add("forest_wall", {"kind": "sprite", "biome": "forest", "tags": ["wall"]})
    cat.add("desert_wall", {"kind": "sprite", "biome": "desert", "tags": ["wall"]})

    sel = Selector(cat)
    pick = sel.select({"kind": "sprite", "biome": "forest", "tags": ["wall"]})
    assert pick is not None
    assert pick["asset_id"] == "forest_wall"


def test_selector_filters_by_kind(tmp_path: Path):
    cat = Catalog(path=tmp_path / "c.json", persist=False, auto_scan_baked=False)
    cat.add("a_sprite", {"kind": "sprite"})
    cat.add("a_tileset", {"kind": "tileset"})

    sel = Selector(cat)
    pick = sel.select({"kind": "tileset"})
    assert pick is not None
    assert pick["asset_id"] == "a_tileset"


def test_selector_returns_none_when_kind_unmatched(tmp_path: Path):
    cat = Catalog(path=tmp_path / "c.json", persist=False, auto_scan_baked=False)
    cat.add("only_sprite", {"kind": "sprite"})
    sel = Selector(cat)
    assert sel.select({"kind": "tileset"}) is None

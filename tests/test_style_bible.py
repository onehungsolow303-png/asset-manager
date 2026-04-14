"""Tests for the style bible reader/writer."""

from __future__ import annotations

from pathlib import Path

from asset_manager.library.style_bible import StyleBible


def test_default_bible_seeded_on_first_load(tmp_path):
    bible_path = tmp_path / "style_bible.json"
    bible = StyleBible(path=bible_path, persist=True, seed_defaults=True)
    assert bible.get_global("art_style") is not None
    assert "D&D" in bible.get_global("art_style")
    assert bible_path.exists()


def test_no_seed_when_seed_defaults_false(tmp_path):
    bible_path = tmp_path / "style_bible.json"
    bible = StyleBible(path=bible_path, persist=True, seed_defaults=False)
    assert bible.get_global("art_style") is None
    assert not bible_path.exists()


def test_get_category_merges_overrides(tmp_path):
    bible = StyleBible(path=tmp_path / "b.json")
    cat = bible.get_category("creature_token")
    # Global art_style should be present in the merged result
    assert "D&D" in cat["art_style"]
    # Override-specific perspective should win
    assert "top-down" in cat["perspective"]


def test_set_global_persists(tmp_path):
    bible_path = tmp_path / "b.json"
    b1 = StyleBible(path=bible_path)
    b1.set_global("art_style", "watercolor")

    # Reload and verify
    b2 = StyleBible(path=bible_path)
    assert b2.get_global("art_style") == "watercolor"


def test_add_global_rule_is_idempotent(tmp_path):
    bible = StyleBible(path=tmp_path / "b.json")
    initial_count = len(bible.get_global("global_rules"))
    bible.add_global_rule("test rule")
    assert len(bible.get_global("global_rules")) == initial_count + 1
    bible.add_global_rule("test rule")  # duplicate
    assert len(bible.get_global("global_rules")) == initial_count + 1


def test_director_preferences_accumulate(tmp_path):
    bible = StyleBible(path=tmp_path / "b.json")
    bible.add_director_approval("ref_001")
    bible.add_director_approval("ref_002")
    bible.add_director_rejection("too_cartoonish")
    bible.add_standing_instruction("always paint with warm light")

    prefs = bible.get_global("director_preferences")
    assert "ref_001" in prefs["approved_references"]
    assert "ref_002" in prefs["approved_references"]
    assert "too_cartoonish" in prefs["rejected_approaches"]
    assert "always paint with warm light" in prefs["standing_instructions"]


def test_render_prompt_preamble_includes_key_fields(tmp_path):
    bible = StyleBible(path=tmp_path / "b.json")
    preamble = bible.render_prompt_preamble("creature_token")
    assert "Style:" in preamble
    assert "Perspective:" in preamble
    assert "Palette:" in preamble
    assert "Rules:" in preamble


def test_set_category_override(tmp_path):
    bible = StyleBible(path=tmp_path / "b.json")
    bible.set_category_override("portrait", "background", "pure black")
    cat = bible.get_category("portrait")
    assert cat["background"] == "pure black"

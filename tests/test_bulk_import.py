"""Tests for the bulk_import CLI."""
from __future__ import annotations

from pathlib import Path

import pytest

from asset_manager.cli.bulk_import import (
    directory_size_mb,
    list_subpacks,
    should_skip,
    slugify,
)


# ─── slugify ────────────────────────────────────────────────────────

def test_slugify_lowercases_and_replaces_special_chars():
    assert slugify("Boss Monster Token Set") == "boss_monster_token_set"
    assert slugify("FA_Tokens_v1.05") == "fa_tokens_v1_05"
    assert slugify("Save Vs. Cave") == "save_vs_cave"


def test_slugify_strips_leading_trailing_separators():
    assert slugify("___Hello___") == "hello"
    assert slugify("...Foo...") == "foo"


def test_slugify_handles_empty_or_special_only():
    assert slugify("") == "pack"
    assert slugify("___") == "pack"


def test_slugify_collapses_runs():
    assert slugify("a   b   c") == "a_b_c"
    assert slugify("a---b---c") == "a_b_c"


# ─── directory_size_mb ──────────────────────────────────────────────

def test_directory_size_empty(tmp_path):
    assert directory_size_mb(tmp_path) == 0.0


def test_directory_size_sums_files(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x" * (1024 * 1024))  # 1 MB
    (tmp_path / "b.bin").write_bytes(b"y" * (512 * 1024))   # 0.5 MB
    size = directory_size_mb(tmp_path)
    assert 1.4 < size < 1.6


def test_directory_size_recursive(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x" * 1024)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.bin").write_bytes(b"y" * 1024)
    size = directory_size_mb(tmp_path)
    assert size == pytest.approx(2 / 1024, rel=0.1)


# ─── list_subpacks ──────────────────────────────────────────────────

def test_list_subpacks_returns_immediate_directories(tmp_path):
    (tmp_path / "pack_a").mkdir()
    (tmp_path / "pack_b").mkdir()
    (tmp_path / "loose_file.txt").write_text("hi")

    subs = list_subpacks(tmp_path)
    names = {p.name for p in subs}
    assert names == {"pack_a", "pack_b"}


def test_list_subpacks_skips_hidden_dirs(tmp_path):
    (tmp_path / "pack").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / ".venv").mkdir()

    subs = list_subpacks(tmp_path)
    names = {p.name for p in subs}
    assert names == {"pack"}


def test_list_subpacks_returns_empty_for_missing_path(tmp_path):
    assert list_subpacks(tmp_path / "ghost") == []


def test_list_subpacks_sorted(tmp_path):
    for name in ("zebra", "apple", "mango"):
        (tmp_path / name).mkdir()
    subs = list_subpacks(tmp_path)
    assert [p.name for p in subs] == ["apple", "mango", "zebra"]


# ─── should_skip ────────────────────────────────────────────────────

def test_should_skip_max_size(tmp_path):
    sub = tmp_path / "big_pack"
    sub.mkdir()
    skip, reason = should_skip(sub, size_mb=1000.0, max_size_mb=500.0,
                                exclude_patterns=[], include_patterns=[])
    assert skip is True
    assert "size" in reason


def test_should_skip_exclude_pattern(tmp_path):
    sub = tmp_path / "Core_Mapmaking_Pack"
    sub.mkdir()
    skip, reason = should_skip(sub, size_mb=10.0, max_size_mb=None,
                                exclude_patterns=["Core_Mapmaking"],
                                include_patterns=[])
    assert skip is True
    assert "Core_Mapmaking" in reason


def test_should_skip_exclude_is_case_insensitive(tmp_path):
    sub = tmp_path / "FA_OBJECTS_A"
    sub.mkdir()
    skip, _ = should_skip(sub, size_mb=10.0, max_size_mb=None,
                           exclude_patterns=["fa_objects"],
                           include_patterns=[])
    assert skip is True


def test_should_skip_include_filter(tmp_path):
    sub = tmp_path / "FA_Tokens_NPCs"
    sub.mkdir()
    skip, _ = should_skip(sub, size_mb=10.0, max_size_mb=None,
                           exclude_patterns=[],
                           include_patterns=["Adversaries"])
    assert skip is True  # not in include list


def test_should_skip_include_filter_match(tmp_path):
    sub = tmp_path / "FA_Tokens_NPCs"
    sub.mkdir()
    skip, _ = should_skip(sub, size_mb=10.0, max_size_mb=None,
                           exclude_patterns=[],
                           include_patterns=["NPCs"])
    assert skip is False


def test_should_skip_returns_false_when_no_filters(tmp_path):
    sub = tmp_path / "any_pack"
    sub.mkdir()
    skip, reason = should_skip(sub, size_mb=10.0, max_size_mb=None,
                                exclude_patterns=[], include_patterns=[])
    assert skip is False
    assert reason == ""

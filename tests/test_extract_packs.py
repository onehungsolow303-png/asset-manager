"""Tests for the extract_packs CLI."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from asset_manager.cli.extract_packs import (
    BatchResult,
    ExtractResult,
    extract_all_in_dir,
    extract_zip,
)


def _make_zip(path: Path, members: dict[str, bytes]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


# ─── extract_zip happy paths ────────────────────────────────────────

def test_extract_zip_extracts_all_members(tmp_path):
    src = _make_zip(tmp_path / "pack.zip", {
        "a.png": b"fake png a",
        "b.png": b"fake png b",
        "sub/c.png": b"fake png c",
    })
    target = tmp_path / "pack"
    result = extract_zip(src, target)

    assert result.success is True
    assert result.skipped is False
    assert result.file_count == 3
    assert (target / "a.png").exists()
    assert (target / "sub" / "c.png").exists()


def test_extract_zip_records_bytes_extracted(tmp_path):
    src = _make_zip(tmp_path / "pack.zip", {
        "a.png": b"x" * 1000,
        "b.png": b"y" * 500,
    })
    result = extract_zip(src, tmp_path / "pack")
    assert result.bytes_extracted == 1500


# ─── Idempotency ────────────────────────────────────────────────────

def test_extract_zip_skips_when_target_already_populated(tmp_path):
    src = _make_zip(tmp_path / "pack.zip", {"a.png": b"x"})
    target = tmp_path / "pack"
    extract_zip(src, target)
    result2 = extract_zip(src, target)
    assert result2.success is True
    assert result2.skipped is True


def test_extract_zip_force_overrides_skip(tmp_path):
    src = _make_zip(tmp_path / "pack.zip", {"a.png": b"x"})
    target = tmp_path / "pack"
    extract_zip(src, target)
    result2 = extract_zip(src, target, force=True)
    assert result2.skipped is False
    assert result2.success is True


def test_extract_zip_skips_when_target_exists_but_empty(tmp_path):
    """Empty target directory should NOT trigger the skip — only
    populated directories are considered already-extracted."""
    src = _make_zip(tmp_path / "pack.zip", {"a.png": b"x"})
    target = tmp_path / "pack"
    target.mkdir()
    result = extract_zip(src, target)
    assert result.skipped is False
    assert result.file_count == 1


# ─── Failure modes ──────────────────────────────────────────────────

def test_extract_zip_fails_on_missing_zip(tmp_path):
    result = extract_zip(tmp_path / "ghost.zip", tmp_path / "out")
    assert result.success is False
    assert "not found" in result.error


def test_extract_zip_fails_on_invalid_zip(tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"this is not a zip file")
    result = extract_zip(bad, tmp_path / "out")
    assert result.success is False
    assert "not a valid zip" in result.error


def test_extract_zip_defends_against_zip_slip(tmp_path):
    """A malicious zip with a path that escapes the target dir
    should NOT have its escape members extracted. The extract should
    succeed for safe members and silently skip the dangerous one."""
    src = tmp_path / "evil.zip"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("safe.txt", b"safe")
        zf.writestr("../escaped.txt", b"escaped")
    target = tmp_path / "out"
    result = extract_zip(src, target)
    assert result.success is True
    assert (target / "safe.txt").exists()
    # The escaped file should NOT have been written outside target
    assert not (tmp_path / "escaped.txt").exists()


# ─── extract_all_in_dir ────────────────────────────────────────────

def test_extract_all_in_dir_processes_each_zip(tmp_path):
    _make_zip(tmp_path / "pack_a.zip", {"a.txt": b"hi"})
    _make_zip(tmp_path / "pack_b.zip", {"b.txt": b"bye"})
    _make_zip(tmp_path / "pack_c.zip", {"c.txt": b"yo"})

    batch = extract_all_in_dir(tmp_path, verbose=False)
    assert batch.successes == 3
    assert batch.failures == 0
    assert (tmp_path / "pack_a" / "a.txt").exists()
    assert (tmp_path / "pack_b" / "b.txt").exists()
    assert (tmp_path / "pack_c" / "c.txt").exists()


def test_extract_all_in_dir_handles_missing_directory(tmp_path):
    batch = extract_all_in_dir(tmp_path / "ghost", verbose=False)
    assert batch.successes == 0
    assert batch.failures == 0
    assert batch.per_zip == []


def test_extract_all_in_dir_skips_non_zip_files(tmp_path):
    _make_zip(tmp_path / "pack.zip", {"a.txt": b"hi"})
    (tmp_path / "readme.txt").write_text("not a zip")
    (tmp_path / "image.png").write_bytes(b"fake png")

    batch = extract_all_in_dir(tmp_path, verbose=False)
    assert batch.successes == 1
    assert len(batch.per_zip) == 1


def test_extract_all_in_dir_continues_after_one_failure(tmp_path):
    _make_zip(tmp_path / "good.zip", {"a.txt": b"hi"})
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")

    batch = extract_all_in_dir(tmp_path, verbose=False)
    assert batch.successes == 1
    assert batch.failures == 1

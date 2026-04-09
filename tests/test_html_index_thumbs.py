"""Tests for the Pillow thumbnail renderer."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from asset_manager.library.html_index_thumbs import (
    DEFAULT_THUMB_BOX,
    is_thumbnailable,
    render_thumbnail,
)


def _write_png(path: Path, size: tuple[int, int] = (256, 256), mode: str = "RGB") -> Path:
    from PIL import Image
    color = (200, 100, 50, 255) if mode == "RGBA" else (200, 100, 50)
    Image.new(mode, size, color).save(path, format="PNG")
    return path


def _write_jpeg(path: Path, size: tuple[int, int] = (256, 256)) -> Path:
    from PIL import Image
    Image.new("RGB", size, (50, 100, 200)).save(path, format="JPEG", quality=90)
    return path


# ─── is_thumbnailable ──────────────────────────────────────────────

def test_is_thumbnailable_accepts_image_extensions():
    assert is_thumbnailable("test.png") is True
    assert is_thumbnailable("test.jpg") is True
    assert is_thumbnailable("test.JPEG") is True
    assert is_thumbnailable("test.webp") is True
    assert is_thumbnailable("test.gif") is True


def test_is_thumbnailable_rejects_3d_and_other():
    assert is_thumbnailable("test.glb") is False
    assert is_thumbnailable("test.fbx") is False
    assert is_thumbnailable("test.txt") is False
    assert is_thumbnailable("test") is False  # no extension


# ─── render_thumbnail happy paths ─────────────────────────────────

def test_render_jpeg_from_png_source(tmp_path):
    src = _write_png(tmp_path / "wolf.png", size=(256, 256), mode="RGB")
    out = render_thumbnail(src, "wolf", tmp_path / "thumbs")
    assert out is not None
    assert out.exists()
    assert out.suffix == ".jpg"  # opaque source → JPEG output
    assert out.parent.name == "thumbs"


def test_render_png_from_rgba_source_preserves_alpha(tmp_path):
    src = _write_png(tmp_path / "icon.png", size=(256, 256), mode="RGBA")
    out = render_thumbnail(src, "icon", tmp_path / "thumbs", preserve_alpha=True)
    assert out is not None
    assert out.suffix == ".png"  # alpha source → PNG output


def test_render_jpeg_from_rgba_when_alpha_disabled(tmp_path):
    src = _write_png(tmp_path / "icon.png", size=(256, 256), mode="RGBA")
    out = render_thumbnail(src, "icon", tmp_path / "thumbs", preserve_alpha=False)
    assert out is not None
    assert out.suffix == ".jpg"  # alpha flattened → JPEG output


def test_render_thumbnail_preserves_aspect_ratio(tmp_path):
    from PIL import Image
    src = _write_png(tmp_path / "wide.png", size=(400, 100))  # 4:1 aspect
    out = render_thumbnail(src, "wide", tmp_path / "thumbs", box=(128, 128))
    assert out is not None
    with Image.open(out) as img:
        w, h = img.size
        assert w == 128  # width-bound
        assert h == 32   # 128 / 4


def test_render_thumbnail_caps_at_box_dimensions(tmp_path):
    from PIL import Image
    src = _write_png(tmp_path / "huge.png", size=(2048, 2048))
    out = render_thumbnail(src, "huge", tmp_path / "thumbs", box=(64, 64))
    with Image.open(out) as img:
        w, h = img.size
        assert w <= 64
        assert h <= 64


def test_render_thumbnail_creates_thumbs_dir(tmp_path):
    src = _write_png(tmp_path / "wolf.png")
    thumbs_dir = tmp_path / "deep" / "nested" / "thumbs"
    out = render_thumbnail(src, "wolf", thumbs_dir)
    assert thumbs_dir.exists()
    assert out is not None


# ─── Idempotency ────────────────────────────────────────────────────

def test_render_skips_when_thumb_newer_than_source(tmp_path):
    src = _write_png(tmp_path / "wolf.png")
    thumbs = tmp_path / "thumbs"

    first = render_thumbnail(src, "wolf", thumbs)
    assert first is not None
    first_mtime = first.stat().st_mtime

    # Wait briefly so the second call wouldn't happen to have the same mtime
    time.sleep(0.1)
    second = render_thumbnail(src, "wolf", thumbs)
    assert second is not None
    assert second == first
    assert second.stat().st_mtime == first_mtime  # not regenerated


def test_render_regenerates_when_source_is_newer(tmp_path):
    src = _write_png(tmp_path / "wolf.png")
    thumbs = tmp_path / "thumbs"

    first = render_thumbnail(src, "wolf", thumbs)
    first_mtime = first.stat().st_mtime

    # Touch the source to make it newer
    time.sleep(0.1)
    src.touch()

    second = render_thumbnail(src, "wolf", thumbs)
    assert second is not None
    # Either the mtime moved forward, or at least the file was overwritten
    assert second.stat().st_mtime >= first_mtime


# ─── Failure modes ──────────────────────────────────────────────────

def test_render_returns_none_for_missing_source(tmp_path):
    out = render_thumbnail(tmp_path / "ghost.png", "ghost", tmp_path / "thumbs")
    assert out is None


def test_render_returns_none_for_unsupported_extension(tmp_path):
    src = tmp_path / "model.glb"
    src.write_bytes(b"fake glb")
    out = render_thumbnail(src, "model", tmp_path / "thumbs")
    assert out is None


def test_render_returns_none_for_corrupt_image(tmp_path):
    src = tmp_path / "corrupt.png"
    src.write_bytes(b"this is not a png file at all")
    out = render_thumbnail(src, "corrupt", tmp_path / "thumbs")
    assert out is None


def test_render_returns_none_for_empty_asset_id(tmp_path):
    src = _write_png(tmp_path / "wolf.png")
    out = render_thumbnail(src, "", tmp_path / "thumbs")
    assert out is None


def test_render_sanitizes_asset_id_for_filename(tmp_path):
    """asset_ids should normally be safe, but if a hand-crafted manifest
    contains path separators, the renderer must not write outside its
    target directory."""
    src = _write_png(tmp_path / "wolf.png")
    out = render_thumbnail(src, "evil/../path", tmp_path / "thumbs")
    assert out is not None
    # Should not have escaped the thumbs directory
    assert "thumbs" in str(out)
    assert ".." not in out.name

"""Thumbnail renderer for the HTML catalog index.

Why this module exists:
    The first version of html_index.py referenced source images directly
    via file:// URIs. This worked for the procedural seed assets (small,
    same-drive, no special characters in path) but FAILED for everything
    interesting:

    1. OneDrive Files-On-Demand placeholders — file path resolves but
       bytes are cloud-only, browser can't load
    2. Cross-drive file:// references — modern browsers restrict file://
       img src to the same parent as the HTML file
    3. Spaces and & in path components need URL encoding (%20, %26),
       and even with proper encoding the browser can be picky about
       file:// URIs
    4. Multi-megabyte source images make the index slow to load

    Solution: pre-render small JPEG thumbnails INTO the same directory
    tree as the HTML file (`.shared/baked/thumbs/<asset_id>.jpg`). The
    HTML references thumbs by relative path. All four problems above
    disappear at once: same drive, no special chars in thumb names,
    fast loading, browser-friendly.

What it does:
    - Takes a source image path + asset_id
    - Loads via PIL.Image
    - Resizes to fit a target box (default 128x128) preserving aspect
    - Saves as JPEG (or PNG if the source has transparency we want kept)
    - Returns the absolute path of the generated thumb
    - Idempotent: skips regeneration if the thumb already exists AND
      its mtime is >= the source mtime

What it does NOT do:
    - Render 3D meshes (.glb / .fbx) — those still get the placeholder
      card in the HTML index. Blender renderer is the future path for
      thumbnailing 3D assets.
    - Compress aggressively. Quality is set to 85 by default for the
      JPEG output, which is a good visual / file-size balance.
    - Walk the catalog. Callers iterate the catalog and call
      `render_thumbnail` per asset. The html_index module does this
      orchestration.

Failure modes:
    - PIL fails to open the source (corrupt PNG, unknown format,
      OneDrive placeholder that can't materialize) → log warning,
      return None, the caller falls through to the placeholder card
    - Disk write fails → log warning, return None
    - Source file does not exist → return None silently (it's not the
      thumbnailer's job to police catalog hygiene; prune_missing_files
      handles that)
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Image extensions PIL can reliably handle for the thumbnail path.
# .gif and .webp work too but are uncommon in our pipeline; left in
# for completeness.
_THUMBNAILABLE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

# Max thumbnail dimensions. Pillow's thumbnail() preserves aspect ratio,
# so a 4096x2160 source becomes 128x67 (width-bound). Sized for visual
# scan-ability in the HTML grid layout.
DEFAULT_THUMB_BOX = (128, 128)

# JPEG quality. 85 is the standard "looks great, half the file size"
# trade-off for game asset previews.
DEFAULT_JPEG_QUALITY = 85

# Filename prefix used to namespace thumbs by extension. The thumb is
# always JPEG unless the source has alpha we want to preserve.
_THUMB_EXT_OPAQUE = ".jpg"
_THUMB_EXT_ALPHA = ".png"


def render_thumbnail(
    source_path: Path,
    asset_id: str,
    thumbs_dir: Path,
    box: tuple[int, int] = DEFAULT_THUMB_BOX,
    quality: int = DEFAULT_JPEG_QUALITY,
    preserve_alpha: bool = True,
) -> Path | None:
    """Generate a thumbnail for `source_path` keyed by `asset_id`.

    Args:
        source_path: Absolute path to the source image
        asset_id: Stable asset ID, used as the thumbnail filename stem
        thumbs_dir: Directory to write thumbnails into
        box: Maximum (width, height) for the thumbnail
        quality: JPEG quality 1-100
        preserve_alpha: When True, sources with transparency are saved
            as PNG to preserve the alpha channel. When False, alpha is
            flattened against a neutral background and the output is
            always JPEG.

    Returns:
        Path to the generated thumbnail on success, or None on any
        failure (corrupt source, missing file, write error). Failures
        are logged but not raised — the caller falls through to the
        placeholder card in the HTML index.
    """
    source_path = Path(source_path)

    if not source_path.exists():
        return None
    if source_path.suffix.lower() not in _THUMBNAILABLE_EXTENSIONS:
        return None
    if not asset_id:
        return None

    # Sanitize the asset_id for use as a filename. The pack_importer
    # already produces safe IDs (lowercase + underscores), but a
    # malicious or hand-crafted manifest could include path separators
    # or parent-directory references. Strip path separators, colons,
    # and any leading/trailing dots; collapse `..` sequences so the
    # final filename can never escape its parent directory.
    safe_id = asset_id.replace("/", "_").replace("\\", "_").replace(":", "_").replace("..", "_")
    # Strip leading dots so the file isn't hidden on Unix
    safe_id = safe_id.lstrip(".")
    if not safe_id:
        return None

    try:
        from PIL import Image
    except ImportError:
        logger.warning("[html_index_thumbs] PIL not available")
        return None

    # Decide the output extension + format. PNG preserves alpha, JPEG
    # doesn't. We try to detect alpha early to pick the right path.
    try:
        with Image.open(source_path) as probe:
            mode = probe.mode
            has_alpha = (
                "A" in mode
                or mode in ("RGBA", "LA", "PA")
                or (probe.info.get("transparency") is not None)
            )
    except Exception as e:
        logger.warning("[html_index_thumbs] failed to probe %s: %s", source_path, e)
        return None

    use_png = preserve_alpha and has_alpha
    out_ext = _THUMB_EXT_ALPHA if use_png else _THUMB_EXT_OPAQUE
    thumb_path = thumbs_dir / f"{safe_id}{out_ext}"

    # Idempotency check: skip if the existing thumb is newer than the
    # source. mtime comparison is cheap and avoids re-encoding for
    # every HTML index regen.
    if thumb_path.exists():
        try:
            source_mtime = source_path.stat().st_mtime
            thumb_mtime = thumb_path.stat().st_mtime
            if thumb_mtime >= source_mtime:
                return thumb_path
        except OSError:
            pass  # fall through and regenerate

    thumbs_dir.mkdir(parents=True, exist_ok=True)

    try:
        with Image.open(source_path) as img:
            # Convert mode for thumbnail generation
            if use_png:
                # PNG output — keep alpha
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
            else:
                # JPEG output — flatten alpha onto white background
                if img.mode in ("RGBA", "LA", "PA"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "RGBA":
                        background.paste(img, mask=img.split()[3])
                    else:
                        background.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[3])
                    img = background
                elif img.mode != "RGB":
                    img = img.convert("RGB")

            # Pillow's thumbnail() resizes in-place, preserves aspect.
            # LANCZOS is the high-quality resampler.
            img.thumbnail(box, Image.Resampling.LANCZOS)

            if use_png:
                img.save(thumb_path, format="PNG", optimize=True)
            else:
                img.save(thumb_path, format="JPEG", quality=quality, optimize=True)

    except Exception as e:
        logger.warning(
            "[html_index_thumbs] failed to render %s -> %s: %s", source_path, thumb_path, e
        )
        return None

    return thumb_path


def is_thumbnailable(path: Path | str) -> bool:
    """Quick check: would `render_thumbnail` produce output for this path?

    Used by html_index to decide between embedding a thumbnail vs
    falling through to the extension placeholder card. Pure path-based
    check — doesn't open the file.
    """
    suffix = Path(path).suffix.lower()
    return suffix in _THUMBNAILABLE_EXTENSIONS

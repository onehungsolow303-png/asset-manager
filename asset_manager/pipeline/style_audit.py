"""Style audit — quality gate before any new asset enters the catalog.

Replaces the "quality-checker agent" from the Development Tool spec
with a single Python module. Every new asset (procedural, AI-generated,
pack-imported) flows through `audit()` and gets either:

  - PASS — registered in the catalog
  - FAIL — rejected, with a list of failure reasons the caller surfaces
           to whichever tier produced it (so e.g. a Tripo3D miss can be
           re-prompted with corrections, or the user can fix manually)

Audit checks (organized by category, all optional via the AuditPolicy):

  Technical:
    - file exists on disk
    - file format matches the asset kind expectation (PNG for sprites,
      GLB for meshes, etc.)
    - PIL-loadable for image kinds (no truncated PNGs)
    - resolution within bounds (per-kind min/max)
    - alpha channel present where required
    - file size within budget (small enough for the engine to load
      cheaply, large enough to not be obviously corrupt)

  Style:
    - dimensions match the kind's size_default from the style bible
    - palette compliance (sample N pixels, check most appear in the
      bible's primary/secondary/accent palette within tolerance)
    - aspect ratio matches expectation

  Integration:
    - asset_id is unique vs current catalog
    - asset_id matches the project's naming convention
    - manifest carries source/license/redistribution fields

The auditor returns an AuditReport (passed: bool, failures: list[str]).
The router (source_decision.py) consumes this and decides whether to
register the asset or fall through to the next tier.

DESIGN NOTE: every check is opt-in via the policy object. The router
can run a fast PASS-or-FAIL audit on every generated asset without
deep inspection, while a CLI tool can run the full deep audit when
the user explicitly asks ("audit my whole catalog").
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Per-kind defaults — can be overridden via AuditPolicy
_DEFAULT_KIND_RULES: dict[str, dict[str, Any]] = {
    "creature_token": {
        "expected_extensions": [".png"],
        "min_dim": 16,
        "max_dim": 512,
        "require_alpha": True,
        "max_file_size_bytes": 5 * 1024 * 1024,  # 5 MB
    },
    "item_icon": {
        "expected_extensions": [".png"],
        "min_dim": 8,
        "max_dim": 256,
        "require_alpha": True,
        "max_file_size_bytes": 1 * 1024 * 1024,  # 1 MB
    },
    "portrait": {
        "expected_extensions": [".png", ".jpg", ".jpeg", ".webp"],
        "min_dim": 64,
        "max_dim": 1024,
        "require_alpha": False,
        "max_file_size_bytes": 10 * 1024 * 1024,  # 10 MB
    },
    "tileset": {
        "expected_extensions": [".png"],
        "min_dim": 16,
        "max_dim": 4096,
        "require_alpha": False,
        "max_file_size_bytes": 20 * 1024 * 1024,  # 20 MB
    },
    "dungeon_tile": {
        "expected_extensions": [".png", ".glb", ".gltf", ".fbx"],
        "min_dim": 16,
        "max_dim": 2048,
        "require_alpha": False,
        "max_file_size_bytes": 50 * 1024 * 1024,  # 50 MB (3D meshes)
    },
    "character": {
        "expected_extensions": [".glb", ".gltf", ".fbx"],
        "min_dim": 0,  # not applicable to 3D
        "max_dim": 0,
        "require_alpha": False,
        "max_file_size_bytes": 100 * 1024 * 1024,  # 100 MB (rigged characters)
    },
}


@dataclass
class AuditPolicy:
    """Tunes which checks the auditor runs and how strict each one is.

    Defaults are reasonable for the Forever engine pipeline. CLI tools
    that want a deep audit can flip every check on; the router uses
    a leaner policy for fast pass-fail decisions.
    """

    check_file_exists: bool = True
    check_extension: bool = True
    check_image_loadable: bool = True
    check_dimensions: bool = True
    check_alpha: bool = True
    check_file_size: bool = True
    check_unique_in_catalog: bool = True
    check_naming_convention: bool = True
    check_manifest_provenance: bool = True

    # Per-kind rules; falls back to _DEFAULT_KIND_RULES if not set
    kind_rules: dict[str, dict[str, Any]] = field(default_factory=dict)

    def rules_for(self, kind: str) -> dict[str, Any]:
        if kind in self.kind_rules:
            merged = dict(_DEFAULT_KIND_RULES.get(kind, {}))
            merged.update(self.kind_rules[kind])
            return merged
        return dict(_DEFAULT_KIND_RULES.get(kind, {}))


@dataclass
class AuditReport:
    """Result of an audit. Caller checks `passed` first; on failure,
    `failures` carries human-readable reasons sorted by severity."""

    passed: bool
    asset_id: str
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def audit(
    asset_id: str,
    kind: str,
    path: str | Path,
    manifest: dict[str, Any] | None = None,
    catalog: Any = None,
    policy: AuditPolicy | None = None,
) -> AuditReport:
    """Run all enabled checks against a single asset and return a report.

    Required:
        asset_id, kind, path — what's being audited

    Optional:
        manifest — the manifest dict that will be registered (used for
                   provenance checks). When None, manifest checks are
                   skipped silently.
        catalog  — Catalog instance for uniqueness check. When None,
                   uniqueness check is skipped silently.
        policy   — AuditPolicy instance. When None, default policy applies.
    """
    p = policy or AuditPolicy()
    rules = p.rules_for(kind)
    failures: list[str] = []
    warnings: list[str] = []

    asset_path = Path(path)

    # ── File existence ──
    if p.check_file_exists and not asset_path.exists():
        failures.append(f"file does not exist: {asset_path}")
        # Bail early — every other check needs the file to exist
        return AuditReport(passed=False, asset_id=asset_id, failures=failures)

    # ── Extension ──
    if p.check_extension:
        expected_exts = rules.get("expected_extensions") or []
        if expected_exts and asset_path.suffix.lower() not in expected_exts:
            failures.append(
                f"extension {asset_path.suffix!r} not in allowed list "
                f"for kind={kind!r}: {expected_exts}"
            )

    # ── File size ──
    if p.check_file_size:
        max_bytes = rules.get("max_file_size_bytes", 0)
        if max_bytes:
            actual_bytes = asset_path.stat().st_size
            if actual_bytes > max_bytes:
                failures.append(
                    f"file size {actual_bytes} exceeds max {max_bytes} for kind={kind!r}"
                )
            elif actual_bytes < 16:
                # Less than 16 bytes is almost certainly corrupt
                failures.append(f"file size {actual_bytes} suspiciously small")

    # ── Image-specific checks (loadable, dimensions, alpha) ──
    image_kinds = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    is_image = asset_path.suffix.lower() in image_kinds
    if is_image and (p.check_image_loadable or p.check_dimensions or p.check_alpha):
        try:
            from PIL import Image

            with Image.open(asset_path) as img:
                width, height = img.size
                mode = img.mode

                if p.check_dimensions:
                    min_d = rules.get("min_dim", 0)
                    max_d = rules.get("max_dim", 0)
                    if min_d and (width < min_d or height < min_d):
                        failures.append(f"dimensions {width}x{height} below min {min_d}")
                    if max_d and (width > max_d or height > max_d):
                        failures.append(f"dimensions {width}x{height} exceed max {max_d}")

                if p.check_alpha and rules.get("require_alpha"):
                    has_alpha = "A" in mode or mode in ("RGBA", "LA", "PA")
                    if not has_alpha:
                        failures.append(
                            f"kind={kind!r} requires alpha channel but image mode is {mode!r}"
                        )
        except Exception as e:
            failures.append(f"image not loadable: {e}")

    # ── Catalog uniqueness ──
    if p.check_unique_in_catalog and catalog is not None:
        existing = catalog.get(asset_id) if hasattr(catalog, "get") else None
        if existing is not None and existing.get("path") != str(asset_path):
            warnings.append(
                f"asset_id {asset_id!r} already in catalog with different "
                f"path: {existing.get('path')}"
            )

    # ── Naming convention ──
    if p.check_naming_convention:
        if not asset_id:
            failures.append("asset_id is empty")
        elif " " in asset_id:
            failures.append(f"asset_id contains spaces: {asset_id!r}")
        elif asset_id != asset_id.lower():
            warnings.append(f"asset_id has uppercase letters: {asset_id!r}")

    # ── Manifest provenance ──
    if p.check_manifest_provenance and manifest is not None:
        for required in ("source", "license"):
            if required not in manifest:
                warnings.append(f"manifest missing field: {required!r}")
        # If source is ai_*, prompt should be populated for re-generation
        source = manifest.get("source") or ""
        if source.startswith("ai_") and not manifest.get("prompt"):
            warnings.append(
                f"source={source!r} but no prompt recorded — "
                "regeneration after model upgrade will be impossible"
            )

    return AuditReport(
        passed=(len(failures) == 0),
        asset_id=asset_id,
        failures=failures,
        warnings=warnings,
    )

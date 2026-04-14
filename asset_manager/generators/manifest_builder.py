"""AssetManifestBuilder - Python port of the archived
ForeverEngine.AssetGeneration.AssetManifestBuilder.cs.

Scans an asset directory for PNG files, classifies each by relative-path
substring, and builds a JSON-serializable manifest. Output JSON shape is
field-compatible with the C# AssetManifest so a Unity-side consumer can
deserialize it without any wrapper changes.

C# reference: C:/Dev/_archive/forever-engine-pre-pivot/Assets/Scripts/AssetGeneration/AssetGeneration/AssetManifestBuilder.cs
Spec: 2026-04-06-csharp-to-python-assetgen-port-design.md §5.3
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image


@dataclass
class AssetEntry:
    id: str
    category: str
    path: str
    format: str
    width: int
    height: int
    tags: list[str]


@dataclass
class AssetManifest:
    version: str = "1.0.0"
    generator: str = "AssetManager"
    created_at: str = ""
    assets: list[AssetEntry] = field(default_factory=list)


def build_manifest(asset_root: Path) -> AssetManifest:
    """Scan asset_root recursively for PNG files and return a manifest.
    Mirrors C# AssetManifestBuilder.Build."""
    manifest = AssetManifest(created_at=datetime.now(UTC).isoformat(timespec="seconds"))
    if not asset_root.exists():
        return manifest

    for file in sorted(asset_root.rglob("*.png")):
        relative = str(file.relative_to(asset_root)).replace("\\", "/")
        asset_id = file.stem
        category = _classify(relative)
        try:
            with Image.open(file) as img:
                width, height = img.size
        except Exception:
            width, height = 0, 0
        manifest.assets.append(
            AssetEntry(
                id=asset_id,
                category=category,
                path=relative,
                format="png",
                width=width,
                height=height,
                tags=[category],
            )
        )
    return manifest


def to_json(manifest: AssetManifest) -> str:
    """Serialize a manifest to JSON. Field-compatible with the C# AssetManifest."""
    return json.dumps(asdict(manifest), indent=2)


def save_manifest(manifest: AssetManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_json(manifest))


def _classify(relative_path: str) -> str:
    """Mirrors the C# substring classification: case-sensitive, first match wins."""
    if "Sprite" in relative_path:
        return "sprite"
    if "Tile" in relative_path:
        return "tileset"
    if "UI" in relative_path:
        return "ui"
    return "texture"

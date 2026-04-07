"""AssetManifestBuilder - Python port of Forever engine's AssetManifestBuilder.cs.

STATUS: STUB. See procedural_sprite.py for the same caveat. A parallel
read-side manifest implementation lives in asset_manager/library/manifest.py;
this stub will be the write-side that bakes generated assets into the library.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


class AssetManifestBuilder:
    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path

    def add(self, asset_id: str, metadata: dict[str, Any]) -> None:
        raise NotImplementedError(
            "AssetManifestBuilder is a stub awaiting C# to Python port. "
            "See spec §14 follow-up #1."
        )

    def build(self) -> dict[str, Any]:
        raise NotImplementedError(
            "AssetManifestBuilder is a stub awaiting C# to Python port. "
            "See spec §14 follow-up #1."
        )

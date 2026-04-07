"""Asset manifest - single-asset metadata helpers. Phase 2 stub."""
from __future__ import annotations

from typing import Any


def make_manifest(asset_id: str, kind: str, path: str, **extra: Any) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "asset_id": asset_id,
        "kind": kind,
        "path": path,
        **extra,
    }

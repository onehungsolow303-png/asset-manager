"""Selection rules - biome/theme/tag matching logic. Phase 2 stub."""
from __future__ import annotations

from typing import Any


def matches(asset: dict[str, Any], request: dict[str, Any]) -> bool:
    if request.get("kind") and asset.get("kind") != request["kind"]:
        return False
    if request.get("biome") and asset.get("biome") != request["biome"]:
        return False
    return True

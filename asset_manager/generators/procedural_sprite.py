"""ProceduralSpriteGenerator - Python port of Forever engine's
ProceduralSpriteGenerator.cs.

STATUS: STUB. Tracked in spec §14 follow-up #1 (C# to Python port).
The original C# implementation is preserved at:
    C:/Dev/_archive/forever-engine-pre-pivot/Assets/Scripts/AssetGeneration/ProceduralSpriteGenerator.cs

Until ported, generate() raises NotImplementedError so callers fail loudly
rather than baking blank sprites into the library.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


class ProceduralSpriteGenerator:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def generate(self, kind: str, biome: str, theme: str, out_path: Path) -> Path:
        raise NotImplementedError(
            "ProceduralSpriteGenerator is a stub awaiting C# to Python port. "
            "See spec §14 follow-up #1."
        )

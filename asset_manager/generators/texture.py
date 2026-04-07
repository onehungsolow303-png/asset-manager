"""TextureGenerator - Python port of Forever engine's TextureGenerator.cs.

STATUS: STUB. See procedural_sprite.py for the same caveat.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


class TextureGenerator:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def generate(self, kind: str, params: dict[str, Any], out_path: Path) -> Path:
        raise NotImplementedError(
            "TextureGenerator is a stub awaiting C# to Python port. "
            "See spec §14 follow-up #1."
        )

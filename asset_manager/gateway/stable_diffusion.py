"""Stable Diffusion gateway. Phase 2 stub."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import GenerationGateway


class StableDiffusionGateway(GenerationGateway):
    name = "stable_diffusion"

    def generate(self, prompt: str, out_path: Path, **kwargs: Any) -> Path:
        raise NotImplementedError("StableDiffusionGateway not yet wired.")

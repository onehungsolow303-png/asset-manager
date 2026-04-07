"""Scenario.gg gateway. Phase 2 stub."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import GenerationGateway


class ScenarioGateway(GenerationGateway):
    name = "scenario"

    def generate(self, prompt: str, out_path: Path, **kwargs: Any) -> Path:
        raise NotImplementedError("ScenarioGateway not yet wired.")

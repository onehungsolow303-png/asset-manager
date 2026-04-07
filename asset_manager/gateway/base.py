"""Generation gateway ABC. Phase 2 stub."""
from __future__ import annotations

import abc
from pathlib import Path
from typing import Any


class GenerationGateway(abc.ABC):
    name: str = "gateway"

    @abc.abstractmethod
    def generate(self, prompt: str, out_path: Path, **kwargs: Any) -> Path: ...

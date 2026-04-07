"""Asset storage - where bytes live on disk. Phase 2 stub."""
from __future__ import annotations

from pathlib import Path

DEFAULT_BAKED_ROOT = Path("C:/Dev/.shared/baked")


class Storage:
    def __init__(self, root: Path = DEFAULT_BAKED_ROOT) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, kind: str, asset_id: str) -> Path:
        return self.root / kind / f"{asset_id}.bin"

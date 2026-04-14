"""Asset storage - where bytes live on disk."""

from __future__ import annotations

from pathlib import Path

DEFAULT_BAKED_ROOT = Path("C:/Dev/.shared/baked")


class Storage:
    def __init__(self, root: Path = DEFAULT_BAKED_ROOT) -> None:
        self.root = root
        # Lazy mkdir: don't create the root until path_for is actually called.
        # This keeps imports side-effect-free.

    def path_for(self, kind: str, asset_id: str, ext: str = "bin") -> Path:
        """Return the on-disk path for an asset of the given kind, id, and extension.

        The kind subdirectory is created on demand. ext is the file extension
        without the leading dot ('png', 'json', 'bin', ...).
        """
        kind_dir = self.root / kind
        kind_dir.mkdir(parents=True, exist_ok=True)
        return kind_dir / f"{asset_id}.{ext}"

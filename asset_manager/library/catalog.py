"""Asset catalog - read-side index of every asset in the library.

Disk-backed: persists to a single JSON file at .shared/state/asset_catalog.json
by default. Loads on construction so set→restart→get works. Can also
auto-scan a baked/ directory tree on construction to discover assets that
were generated outside this catalog instance (e.g., by the bake CLI).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CATALOG_PATH = Path("C:/Dev/.shared/state/asset_catalog.json")
DEFAULT_BAKED_ROOT = Path("C:/Dev/.shared/baked")


class Catalog:
    def __init__(
        self,
        path: Path | None = None,
        persist: bool = True,
        auto_scan_baked: bool = True,
        baked_root: Path | None = None,
    ) -> None:
        self._by_id: dict[str, dict[str, Any]] = {}
        self._path = path or DEFAULT_CATALOG_PATH
        self._persist = persist
        if self._persist and self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._by_id = data
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("[Catalog] failed to load %s: %s", self._path, e)

        if auto_scan_baked:
            root = baked_root or DEFAULT_BAKED_ROOT
            self._scan_baked(root)

    def add(self, asset_id: str, manifest: dict[str, Any]) -> None:
        # Ensure the manifest carries its own asset_id so search/get round-trip
        manifest = dict(manifest)
        manifest.setdefault("asset_id", asset_id)
        self._by_id[asset_id] = manifest
        self._save()

    def get(self, asset_id: str) -> dict[str, Any] | None:
        return self._by_id.get(asset_id)

    def search(self, **filters: Any) -> list[dict[str, Any]]:
        """Exact-match search across the catalog. Returns a list of manifests
        whose fields equal all of the supplied filter values."""
        out = []
        for m in self._by_id.values():
            if all(m.get(k) == v for k, v in filters.items()):
                out.append(m)
        return out

    def all(self) -> list[dict[str, Any]]:
        return list(self._by_id.values())

    def count(self) -> int:
        return len(self._by_id)

    def remove(self, asset_id: str) -> bool:
        if asset_id not in self._by_id:
            return False
        del self._by_id[asset_id]
        self._save()
        return True

    def wipe(self) -> None:
        """Clear in-memory and delete the on-disk file."""
        self._by_id.clear()
        if self._persist and self._path.exists():
            self._path.unlink()

    def _save(self) -> None:
        if not self._persist:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._by_id, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning("[Catalog] persist failed: %s", e)

    def _scan_baked(self, root: Path) -> None:
        """Walk root looking for PNGs and add any not already in the catalog.

        Each PNG at <root>/<kind>/<asset_id>.png becomes a manifest with
        kind=<dir>, asset_id=<stem>, path=<absolute path>. Existing entries
        with the same asset_id are not overwritten so manual edits stick.
        """
        if not root.exists():
            return
        added = 0
        for path in sorted(root.rglob("*.png")):
            try:
                rel = path.relative_to(root)
            except ValueError:
                continue
            parts = rel.parts
            if len(parts) < 2:
                continue
            kind = parts[0]
            asset_id = path.stem
            if asset_id in self._by_id:
                continue
            self._by_id[asset_id] = {
                "asset_id": asset_id,
                "kind": kind,
                "path": str(path),
            }
            added += 1
        if added > 0:
            logger.info("[Catalog] scanned %s, added %d assets", root, added)
            self._save()

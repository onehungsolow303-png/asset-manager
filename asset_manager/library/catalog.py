"""Asset catalog - read-side index of every asset in the library.

Disk-backed: persists to a single JSON file at .shared/state/asset_catalog.json
by default. Loads on construction so set→restart→get works. Can also
auto-scan a baked/ directory tree on construction to discover assets that
were generated outside this catalog instance (e.g., by the bake CLI).

On load, every entry is run through `manifest.migrate_manifest` so legacy
catalog entries get the new provenance fields (source, license, cost_usd,
swap_safe, etc.) inferred from their path. The migration is idempotent —
already-migrated entries are no-ops.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from asset_manager.library.manifest import migrate_manifest

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
        prune_on_load: bool = True,
    ) -> None:
        self._by_id: dict[str, dict[str, Any]] = {}
        self._path = path or DEFAULT_CATALOG_PATH
        self._persist = persist
        # Always load from disk if the file exists, regardless of `persist`.
        # The persist flag controls WRITES (whether .add()/.remove() flush
        # to disk), not READS. Read-only audit tools (like
        # cli/ship_export_check.py) need to load the on-disk state without
        # accidentally persisting any migrations they trigger.
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._by_id = data
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("[Catalog] failed to load %s: %s", self._path, e)

        # Drop stale entries (deleted/moved files, leftover pytest temp
        # paths) BEFORE auto-scan so the auto-scan doesn't have to compete
        # with phantom records. Off by default for tests that supply a
        # known-good catalog dict.
        if prune_on_load:
            self.prune_missing_files()

        # Migrate every loaded entry to the new manifest schema. Inferred
        # provenance is filled in for legacy entries (source/license from
        # path), and missing fields get safe defaults. Idempotent — entries
        # that already have the new schema are no-ops, so this is safe to
        # run on every startup.
        self._migrate_all()

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

    def _migrate_all(self) -> int:
        """Run manifest.migrate_manifest on every catalog entry.

        Idempotent: entries that already have the new schema fields are
        not modified. Returns the count of entries that were touched
        (had new fields added). Persists once at the end if anything
        changed, so a no-op startup costs zero disk writes.
        """
        before = json.dumps(self._by_id, sort_keys=True, default=str)
        for manifest in self._by_id.values():
            migrate_manifest(manifest)
        after = json.dumps(self._by_id, sort_keys=True, default=str)
        if before != after:
            logger.info("[Catalog] migrated entries to new manifest schema")
            self._save()
            return 1
        return 0

    def prune_missing_files(self) -> int:
        """Remove every catalog entry whose `path` no longer exists on disk.

        Catalogs accumulate stale references over time — pytest temp dirs
        get cleaned up between runs, manually-deleted bakes stay registered,
        moved files orphan their old entries. This sweep walks every entry
        and drops the ones whose path can't be opened.

        Idempotent and safe: in-memory entries with no `path` field are
        left alone (they may be partial manifests under construction).

        Returns the count of pruned entries. Persists once at the end so
        pruning N stale entries is one disk write, not N.
        """
        stale: list[str] = []
        for asset_id, manifest in self._by_id.items():
            raw_path = manifest.get("path")
            if not raw_path:
                continue
            try:
                if not Path(raw_path).exists():
                    stale.append(asset_id)
            except (OSError, ValueError):
                # Path() can raise ValueError on certain Windows paths
                # (NUL chars, etc); treat unparseable paths as stale.
                stale.append(asset_id)

        for asset_id in stale:
            del self._by_id[asset_id]

        if stale:
            logger.info(
                "[Catalog] pruned %d stale entries with missing files",
                len(stale),
            )
            self._save()
        return len(stale)

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

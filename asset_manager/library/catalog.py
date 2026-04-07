"""Asset catalog - read-side index. Phase 2 stub: in-memory dict."""
from __future__ import annotations

from typing import Any


class Catalog:
    def __init__(self) -> None:
        self._by_id: dict[str, dict[str, Any]] = {}

    def add(self, asset_id: str, manifest: dict[str, Any]) -> None:
        self._by_id[asset_id] = manifest

    def get(self, asset_id: str) -> dict[str, Any] | None:
        return self._by_id.get(asset_id)

    def search(self, **filters: Any) -> list[dict[str, Any]]:
        out = []
        for m in self._by_id.values():
            if all(m.get(k) == v for k, v in filters.items()):
                out.append(m)
        return out

    def all(self) -> list[dict[str, Any]]:
        return list(self._by_id.values())

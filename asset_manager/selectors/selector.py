"""Selector - given a SelectionRequest, return the best matching asset.

Phase 2 stub. Always returns None (miss) so the bridge can exercise the
miss-path. Real selector queries Catalog by tags/biome/theme.
"""
from __future__ import annotations

from typing import Any


class Selector:
    def __init__(self, catalog: Any) -> None:
        self.catalog = catalog

    def select(self, request: dict[str, Any]) -> dict[str, Any] | None:
        return None

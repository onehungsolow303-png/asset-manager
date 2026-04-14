"""Selector - given a SelectionRequest, return the best matching asset.

Real implementation backed by the Catalog. For each candidate that passes
`rules.matches`, score with `rules.score` and return the highest. Returns
None when no candidate matches.
"""

from __future__ import annotations

from typing import Any

from . import rules


class Selector:
    def __init__(self, catalog: Any) -> None:
        self.catalog = catalog

    def select(self, request: dict[str, Any]) -> dict[str, Any] | None:
        candidates = [asset for asset in self.catalog.all() if rules.matches(asset, request)]
        if not candidates:
            return None
        # Highest score wins. Stable sort: in case of a tie, the asset that
        # was indexed first wins (first-match-by-id has lower entropy).
        candidates.sort(key=lambda a: rules.score(a, request), reverse=True)
        return candidates[0]

"""Selection matching rules.

Used by Selector to filter the catalog down to candidates that satisfy
the SelectionRequest. The matcher is intentionally tolerant: missing
fields on EITHER side don't disqualify a candidate, but mismatched
explicit values do. Tags use set-overlap (any common tag matches).
"""

from __future__ import annotations

from typing import Any


def matches(asset: dict[str, Any], request: dict[str, Any]) -> bool:
    """Return True if the asset can satisfy the request.

    Rules:
    - kind: must match exactly if request.kind is set.
    - biome: must match if both request.biome and asset.biome are set.
              If asset has no biome, it's a generic asset that matches.
    - theme: same as biome.
    - tags: if request.tags is non-empty, the asset must share at least
             one tag (set overlap). Empty request.tags accepts everything.
    """
    if request.get("kind") and asset.get("kind") != request["kind"]:
        return False

    biome = request.get("biome")
    if biome and asset.get("biome") and asset["biome"] != biome:
        return False

    theme = request.get("theme")
    if theme and asset.get("theme") and asset["theme"] != theme:
        return False

    req_tags = set(request.get("tags") or [])
    if req_tags:
        asset_tags = set(asset.get("tags") or [])
        if asset_tags and not (req_tags & asset_tags):
            return False

    return True


def score(asset: dict[str, Any], request: dict[str, Any]) -> int:
    """Score how well asset matches request. Higher is better.

    Used for ranking when multiple candidates pass `matches()`. Counts
    explicit field matches: kind, biome, theme, plus the size of the
    tag intersection.
    """
    s = 0
    if request.get("kind") and asset.get("kind") == request["kind"]:
        s += 4
    if request.get("biome") and asset.get("biome") == request["biome"]:
        s += 3
    if request.get("theme") and asset.get("theme") == request["theme"]:
        s += 2
    req_tags = set(request.get("tags") or [])
    asset_tags = set(asset.get("tags") or [])
    s += len(req_tags & asset_tags)
    return s

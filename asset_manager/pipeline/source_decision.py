"""Source-decision protocol — the deterministic asset routing layer.

Given an asset request (kind + tags + biome + optional prompt), this
module walks a layered fallback chain in cost order and returns the
first tier that produces a usable asset. The intent is the same as the
RecordReplayProvider cassette pattern in Director Hub: deterministic,
cache-first, cost-aware, and the cheapest tier always tried first.

The chain (low cost → high cost):

  1. CACHE          — content-addressable lookup by request hash. If
                       a previous identical request produced an asset,
                       return it immediately. $0.

  2. LIBRARY        — query the catalog via the existing /select
                       semantics (kind + biome + tags). Hits any
                       previously-imported pack asset. $0.

  3. PROCEDURAL     — match against registered procedural recipes
                       (the existing creature_token / item_icon /
                       texture / tileset generators). $0.

  4. LOCAL_LORA_SD  — local Stable Diffusion + style-trained LoRA.
                       Generates a fresh 2D asset in the user's
                       trained art style. $0 with RTX 5090, but slower
                       than the above tiers (5-15 seconds per asset).
                       Requires the LoRA to have been trained.

  5. NANO_BANANA    — Google Gemini 2.5 Flash Image. Cheap cloud edits
                       (~$0.04 per generation) for image-to-image work
                       like turning a Roll20 source into a derivative.
                       Requires GEMINI_API_KEY.

  6. TRIPO3D        — Tripo3D image-to-3D mesh. Most expensive tier.
                       Only invoked when an explicit 3D mesh is
                       requested (kind=mesh) or when 2D tiers all
                       miss for a unique asset. ~$0.10-1.00 per call.
                       Requires TRIPO_API_KEY.

CACHE WRITE-THROUGH:

Every successful generation from a non-cache tier is written back to
the catalog with `source` set to the tier that produced it (procedural,
ai_2d, ai_3d, etc.) and `cost_usd` populated. The next request for
the same semantic asset hits CACHE and skips the expensive tiers.

BUDGET CEILING:

A per-session spend ceiling (default $1.00) prevents runaway loops
from emptying API credits. The router tracks cumulative cost across
all generations in the current process. When the ceiling is reached,
all paid tiers are SKIPPED and the router falls through to the next
free tier or returns a miss.

NOT YET WIRED INTO THE BRIDGE:

This module is the routing primitive. It's not yet plugged into the
/generate endpoint — that wiring is a Batch 3 task that needs the
user's approval to actually start charging API credits. For now,
the router exists, is unit-tested, and can be invoked from CLI tools
or future endpoints once budgets and keys are confirmed.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class Tier(str, Enum):
    """Routing tiers, ordered cheapest → most expensive."""
    CACHE = "cache"
    LIBRARY = "library"
    PROCEDURAL = "procedural"
    LOCAL_LORA_SD = "local_lora_sd"
    NANO_BANANA = "nano_banana"
    TRIPO3D = "tripo3d"


# Approximate cost per generation, USD. Used for budget tracking.
# These are best-effort estimates; the real Tripo / Gemini bills land
# in your account dashboard. Tune these as you observe actual usage.
TIER_COST_USD: dict[Tier, float] = {
    Tier.CACHE: 0.0,
    Tier.LIBRARY: 0.0,
    Tier.PROCEDURAL: 0.0,
    Tier.LOCAL_LORA_SD: 0.0,  # local GPU = effectively free
    Tier.NANO_BANANA: 0.04,    # Gemini 2.5 Flash Image, per edit
    Tier.TRIPO3D: 0.30,        # rough average; image-to-3D is ~1 credit
}

PAID_TIERS = {Tier.NANO_BANANA, Tier.TRIPO3D}


@dataclass
class AssetRequest:
    """Everything the router needs to make a routing decision.

    The hash function uses kind + tags + biome + style + constraints +
    prompt — but explicitly NOT session_id, request_id, or any other
    transient field. Two requests for the same semantic asset must
    produce the same hash so the cache lookup hits.
    """
    kind: str
    tags: list[str] = field(default_factory=list)
    biome: str | None = None
    style: str | None = None
    prompt: str | None = None
    constraints: dict[str, Any] = field(default_factory=dict)

    def hash(self) -> str:
        """SHA256 of canonical-JSON, sorted keys, transient fields stripped."""
        canonical = {
            "kind": self.kind,
            "tags": sorted(self.tags),
            "biome": self.biome,
            "style": self.style,
            "prompt": self.prompt,
            "constraints": self.constraints,
        }
        blob = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class RoutingResult:
    """What the router returns for a given request."""
    found: bool
    tier: Tier | None = None
    asset_id: str | None = None
    path: str | None = None
    manifest: dict[str, Any] | None = None
    cost_usd: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class TierConfig:
    """Per-tier configuration. The router queries each tier in order
    and skips ones marked enabled=False or ones whose handler is None."""
    tier: Tier
    enabled: bool = True
    handler: Callable[[AssetRequest], RoutingResult | None] | None = None


class SourceDecisionRouter:
    """The deterministic protocol router.

    Construction:
        router = SourceDecisionRouter(
            tiers=[TierConfig(Tier.CACHE, handler=...), ...],
            budget_ceiling_usd=1.0,
        )

    Usage:
        result = router.route(AssetRequest(kind="creature_token", tags=["wolf"]))
        if result.found:
            return result.asset_id, result.path
    """

    def __init__(
        self,
        tiers: list[TierConfig],
        budget_ceiling_usd: float = 1.0,
    ) -> None:
        self._tiers = tiers
        self._budget_ceiling_usd = float(budget_ceiling_usd)
        self._spent_usd: float = 0.0

    @property
    def spent_usd(self) -> float:
        return self._spent_usd

    @property
    def budget_remaining_usd(self) -> float:
        return max(0.0, self._budget_ceiling_usd - self._spent_usd)

    def reset_budget(self) -> None:
        """Zero the cumulative spend counter (per-session reset)."""
        self._spent_usd = 0.0

    def route(self, request: AssetRequest) -> RoutingResult:
        """Walk tiers in order, return the first hit. Always returns a
        RoutingResult — found=False with notes=["no tier matched"] when
        every tier misses. Never raises (handler exceptions are caught
        and logged so a single tier failure can't kill the chain)."""
        notes_collected: list[str] = []

        for cfg in self._tiers:
            if not cfg.enabled:
                notes_collected.append(f"{cfg.tier.value}: disabled")
                continue
            if cfg.handler is None:
                notes_collected.append(f"{cfg.tier.value}: no handler")
                continue

            # Budget gate for paid tiers — skip them if we'd exceed
            # the ceiling. The router still tries cheaper-or-equal
            # tiers below this point.
            if cfg.tier in PAID_TIERS:
                projected = self._spent_usd + TIER_COST_USD[cfg.tier]
                if projected > self._budget_ceiling_usd:
                    notes_collected.append(
                        f"{cfg.tier.value}: skipped (budget ceiling "
                        f"${self._budget_ceiling_usd:.2f}, projected "
                        f"${projected:.2f})"
                    )
                    continue

            try:
                result = cfg.handler(request)
            except Exception as e:  # boundary - don't let one tier kill the chain
                logger.warning(
                    "[router] tier %s handler raised: %s", cfg.tier.value, e
                )
                notes_collected.append(f"{cfg.tier.value}: error: {e}")
                continue

            if result is None:
                notes_collected.append(f"{cfg.tier.value}: miss")
                continue
            if not result.found:
                notes_collected.append(f"{cfg.tier.value}: explicit miss")
                continue

            # HIT! Tag the result with the tier that served it, charge
            # the budget if the tier is paid, and return.
            result.tier = cfg.tier
            cost = TIER_COST_USD.get(cfg.tier, 0.0)
            result.cost_usd = cost
            self._spent_usd += cost
            result.notes = notes_collected + [
                f"{cfg.tier.value}: HIT ${cost:.4f}"
            ]
            logger.info(
                "[router] %s -> %s (asset_id=%s, cost=$%.4f, total=$%.4f)",
                request.kind, cfg.tier.value, result.asset_id, cost, self._spent_usd,
            )
            return result

        # All tiers exhausted
        return RoutingResult(found=False, notes=notes_collected + ["no tier matched"])

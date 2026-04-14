"""Tests for the source-decision routing protocol."""

from __future__ import annotations

import pytest

from asset_manager.pipeline.source_decision import (
    PAID_TIERS,
    TIER_COST_USD,
    AssetRequest,
    RoutingResult,
    SourceDecisionRouter,
    Tier,
    TierConfig,
)

# ─── AssetRequest hashing ─────────────────────────────────────────


def test_hash_is_deterministic():
    req1 = AssetRequest(kind="creature_token", tags=["wolf"], biome="forest")
    req2 = AssetRequest(kind="creature_token", tags=["wolf"], biome="forest")
    assert req1.hash() == req2.hash()


def test_hash_is_tag_order_independent():
    req1 = AssetRequest(kind="creature_token", tags=["wolf", "forest"])
    req2 = AssetRequest(kind="creature_token", tags=["forest", "wolf"])
    assert req1.hash() == req2.hash()


def test_hash_changes_with_different_kind():
    req1 = AssetRequest(kind="creature_token", tags=["wolf"])
    req2 = AssetRequest(kind="portrait", tags=["wolf"])
    assert req1.hash() != req2.hash()


def test_hash_changes_with_different_prompt():
    req1 = AssetRequest(kind="creature_token", prompt="a wolf in moonlight")
    req2 = AssetRequest(kind="creature_token", prompt="a wolf at noon")
    assert req1.hash() != req2.hash()


# ─── Routing through tiers ────────────────────────────────────────


def _hit(asset_id: str = "wolf") -> RoutingResult:
    return RoutingResult(found=True, asset_id=asset_id, path=f"/x/{asset_id}.png")


def _miss() -> RoutingResult:
    return RoutingResult(found=False)


def test_router_returns_first_hit():
    """The first tier with a hit wins; later tiers are not consulted."""
    consulted: list[str] = []

    def cache_handler(req):
        consulted.append("cache")
        return _miss()

    def library_handler(req):
        consulted.append("library")
        return _hit("wolf")

    def proc_handler(req):
        consulted.append("procedural")
        return _hit("should_not_be_called")

    router = SourceDecisionRouter(
        tiers=[
            TierConfig(Tier.CACHE, handler=cache_handler),
            TierConfig(Tier.LIBRARY, handler=library_handler),
            TierConfig(Tier.PROCEDURAL, handler=proc_handler),
        ],
    )
    result = router.route(AssetRequest(kind="creature_token", tags=["wolf"]))

    assert result.found is True
    assert result.tier == Tier.LIBRARY
    assert result.asset_id == "wolf"
    assert consulted == ["cache", "library"]  # procedural was NOT called
    assert result.cost_usd == 0.0


def test_router_misses_when_all_tiers_miss():
    router = SourceDecisionRouter(
        tiers=[
            TierConfig(Tier.CACHE, handler=lambda r: _miss()),
            TierConfig(Tier.LIBRARY, handler=lambda r: _miss()),
        ],
    )
    result = router.route(AssetRequest(kind="creature_token"))
    assert result.found is False
    assert result.tier is None
    assert "no tier matched" in result.notes[-1]


def test_router_skips_disabled_tiers():
    consulted: list[str] = []

    def hit_handler(req):
        consulted.append("hit")
        return _hit("never_called")

    def fallback_handler(req):
        consulted.append("fallback")
        return _hit("fallback_asset")

    router = SourceDecisionRouter(
        tiers=[
            TierConfig(Tier.LIBRARY, enabled=False, handler=hit_handler),
            TierConfig(Tier.PROCEDURAL, handler=fallback_handler),
        ],
    )
    result = router.route(AssetRequest(kind="creature_token"))
    assert result.found is True
    assert result.tier == Tier.PROCEDURAL
    assert consulted == ["fallback"]
    assert result.asset_id == "fallback_asset"


def test_router_handler_exception_does_not_kill_chain():
    """A tier handler that raises should be logged and skipped, not
    propagated. The router moves to the next tier."""

    def boom(req):
        raise RuntimeError("tier exploded")

    def fallback(req):
        return _hit("recovered")

    router = SourceDecisionRouter(
        tiers=[
            TierConfig(Tier.NANO_BANANA, handler=boom),
            TierConfig(Tier.PROCEDURAL, handler=fallback),
        ],
        budget_ceiling_usd=10.0,
    )
    result = router.route(AssetRequest(kind="creature_token"))
    assert result.found is True
    assert result.tier == Tier.PROCEDURAL
    assert any("error" in n for n in result.notes)


# ─── Budget ceiling ────────────────────────────────────────────────


def test_paid_tiers_skipped_when_budget_exceeded():
    """Paid tiers (NANO_BANANA, TRIPO3D) must be skipped when projected
    spend would exceed the ceiling. Free tiers continue normally."""
    consulted: list[str] = []

    def nano_handler(req):
        consulted.append("nano")
        return _hit("nano_asset")

    def free_fallback(req):
        consulted.append("free")
        return _hit("free_asset")

    router = SourceDecisionRouter(
        tiers=[
            TierConfig(Tier.NANO_BANANA, handler=nano_handler),
            TierConfig(Tier.PROCEDURAL, handler=free_fallback),
        ],
        budget_ceiling_usd=0.001,  # tiny budget — nano costs $0.04
    )
    result = router.route(AssetRequest(kind="creature_token"))
    assert result.found is True
    assert result.tier == Tier.PROCEDURAL  # nano was skipped
    assert "nano" not in consulted
    assert "free" in consulted


def test_paid_tier_charges_budget_on_hit():
    def nano_handler(req):
        return _hit("nano_asset")

    router = SourceDecisionRouter(
        tiers=[TierConfig(Tier.NANO_BANANA, handler=nano_handler)],
        budget_ceiling_usd=10.0,
    )
    assert router.spent_usd == 0.0
    router.route(AssetRequest(kind="creature_token"))
    assert router.spent_usd == TIER_COST_USD[Tier.NANO_BANANA]


def test_reset_budget_zeros_spend():
    router = SourceDecisionRouter(
        tiers=[TierConfig(Tier.NANO_BANANA, handler=lambda r: _hit())],
        budget_ceiling_usd=10.0,
    )
    router.route(AssetRequest(kind="creature_token"))
    assert router.spent_usd > 0
    router.reset_budget()
    assert router.spent_usd == 0.0


def test_budget_remaining_is_clamped_at_zero():
    router = SourceDecisionRouter(
        tiers=[TierConfig(Tier.NANO_BANANA, handler=lambda r: _hit())],
        budget_ceiling_usd=0.01,
    )
    router.route(AssetRequest(kind="creature_token"))
    # nano costs more than the ceiling, so remaining should be 0 not negative
    assert router.budget_remaining_usd >= 0.0


# ─── Result tagging ────────────────────────────────────────────────


def test_result_carries_serving_tier():
    router = SourceDecisionRouter(
        tiers=[TierConfig(Tier.CACHE, handler=lambda r: _hit("cache_asset"))],
    )
    result = router.route(AssetRequest(kind="creature_token"))
    assert result.tier == Tier.CACHE
    assert result.cost_usd == 0.0
    assert any("HIT" in n for n in result.notes)

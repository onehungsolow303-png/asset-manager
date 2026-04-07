"""
LootAgent — Distributes treasure budget across rooms using three pools:
  - main_pool   (60 %): combat/utility rooms, proportional to risk-reward score
  - boss_pool   (25 %): boss node only
  - exploration_pool (15 %): secret/hidden rooms, split evenly

Risk-reward score per room combines encounter XP, trap danger, and zone depth,
then scaled by the room's loot_mult from ROOM_PURPOSES.
"""

from typing import Any

import numpy as np

from .base_agent import BaseAgent
from asset_manager.shared_state import SharedState

# Exploration purposes that draw from the exploration pool instead of main pool.
_EXPLORATION_PURPOSES = {"secret_chamber", "hidden_cellar"}

# Loot composition profiles per purpose
_LOOT_PROFILES: dict[str, list[tuple[str, float]]] = {
    # (item_type, probability_weight)
    "treasure_vault": [("gold", 0.60), ("gem", 0.30), ("magic_item", 0.10)],
    "armory":         [("weapon", 0.70), ("armor", 0.20), ("magic_weapon", 0.10)],
    "boss_lair":      [("gold", 0.50), ("best_item", 0.30), ("gem", 0.20)],
}
_DEFAULT_LOOT_PROFILE: list[tuple[str, float]] = [("gold", 0.80), ("minor_item", 0.20)]


def _build_loot(purpose: str, gold_value: int, rng: np.random.Generator) -> dict:
    """Convert a gold value into a loot dict with gold + optional item list."""
    profile = _LOOT_PROFILES.get(purpose, _DEFAULT_LOOT_PROFILE)

    # Weighted pick of composition
    types, weights = zip(*profile)
    weights_arr = np.array(weights, dtype=float)
    weights_arr /= weights_arr.sum()  # normalise

    gold = 0
    items: list[dict] = []

    if gold_value <= 0:
        return {"gold": 0, "items": []}

    # Determine primary allocation
    chosen = rng.choice(len(types), p=weights_arr)
    chosen_type = types[chosen]

    if chosen_type == "gold":
        gold = gold_value
    else:
        # Non-gold primary: split ~60 % gold, remainder becomes an item
        gold = int(gold_value * 0.6)
        item_value = gold_value - gold
        items.append({"type": chosen_type, "value": item_value})

    # Small chance for a bonus minor item in treasure-rich rooms
    if purpose in ("treasure_vault", "boss_lair") and rng.random() < 0.5:
        bonus_roll = rng.integers(10, 50)
        items.append({"type": "minor_item", "value": int(bonus_roll)})

    return {"gold": gold, "items": items}


class LootAgent(BaseAgent):
    """Distributes treasure budget to rooms via three-pool risk-reward system."""

    name = "LootAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        from data.game_tables import TREASURE_TABLE, LOOT_TIER_MULT
        from data.room_purposes import ROOM_PURPOSES

        graph = shared_state.room_graph
        if graph is None:
            return {"skipped": True}

        rng = np.random.default_rng(shared_state.config.seed + 1300)

        profile: dict = params.get("profile", {})
        party_level: int = int(params.get("party_level", 5))
        party_size: int = int(params.get("party_size", 4))

        # ── Budget calculation ────────────────────────────────────────────────
        base_gold = TREASURE_TABLE.get(party_level, TREASURE_TABLE[5]) * party_size
        tier_mult = LOOT_TIER_MULT.get(profile.get("loot_tier", "medium"), 1.0)
        total_budget = int(base_gold * tier_mult)
        main_pool = int(total_budget * 0.60)
        boss_pool = int(total_budget * 0.25)
        exploration_pool = total_budget - main_pool - boss_pool  # ~15 %

        # ── Identify secret edges (exploration rooms by connectivity) ─────────
        secret_connected: set[str] = set()
        for edge in graph.edges:
            if edge.connection_type == "secret":
                secret_connected.add(edge.to_id)
                secret_connected.add(edge.from_id)

        # ── Classify nodes ────────────────────────────────────────────────────
        boss_nodes: list = []
        exploration_nodes: list = []
        main_nodes: list = []
        entrance_node_ids: set[str] = set()

        for node in graph.nodes:
            purpose = getattr(node, "purpose", None) or ""
            if "entrance" in node.tags or purpose == "entrance":
                entrance_node_ids.add(node.node_id)
            elif "boss" in node.tags or purpose == "boss_lair":
                boss_nodes.append(node)
            elif purpose in _EXPLORATION_PURPOSES or node.node_id in secret_connected:
                exploration_nodes.append(node)
            else:
                main_nodes.append(node)

        # ── Risk-reward scoring ───────────────────────────────────────────────
        max_xp = max(
            (n.metadata.get("encounter", {}).get("xp", 0) for n in graph.nodes),
            default=0,
        ) or 1
        max_zone = graph.max_zone or 1

        for node in graph.nodes:
            xp = node.metadata.get("encounter", {}).get("xp", 0)
            trap_data = node.metadata.get("trap")
            danger = (
                trap_data.get("danger_score", 0) if isinstance(trap_data, dict) else 0
            )
            depth = node.zone / max_zone
            risk = (xp / max_xp) * 0.5 + danger * 0.3 + depth * 0.2
            purpose = getattr(node, "purpose", None) or ""
            loot_mult = ROOM_PURPOSES.get(purpose, {}).get("loot_mult", 0.5)
            node.metadata["_risk_score"] = risk * loot_mult

        total_distributed = 0
        rooms_with_loot = 0

        # ── Distribute exploration_pool ───────────────────────────────────────
        if exploration_nodes:
            # Weight by risk score; fall back to equal split if all zero
            exp_scores = np.array(
                [max(n.metadata.get("_risk_score", 0), 0.01) for n in exploration_nodes], dtype=float
            )
            exp_scores /= exp_scores.sum()
            for node, share in zip(exploration_nodes, exp_scores):
                alloc = int(exploration_pool * share)
                loot = _build_loot(node.purpose or "", alloc, rng)
                node.metadata["loot"] = loot
                if loot["gold"] > 0 or loot["items"]:
                    rooms_with_loot += 1
                total_distributed += loot["gold"] + sum(
                    i.get("value", 0) for i in loot["items"]
                )

        # ── Distribute main_pool ──────────────────────────────────────────────
        eligible_main = [n for n in main_nodes if n.node_id not in entrance_node_ids]
        if eligible_main:
            scores = np.array(
                [max(n.metadata.get("_risk_score", 0), 0.0) for n in eligible_main], dtype=float
            )
            total_score = scores.sum()
            if total_score <= 0:
                # Equal distribution fallback
                scores = np.ones(len(eligible_main), dtype=float)
                total_score = float(len(eligible_main))
            shares = scores / total_score
            for node, share in zip(eligible_main, shares):
                alloc = int(main_pool * share)
                loot = _build_loot(node.purpose or "", alloc, rng)
                node.metadata["loot"] = loot
                if loot["gold"] > 0 or loot["items"]:
                    rooms_with_loot += 1
                total_distributed += loot["gold"] + sum(
                    i.get("value", 0) for i in loot["items"]
                )

        # ── Distribute boss_pool ──────────────────────────────────────────────
        # Boss gold is set after main_pool so we can guarantee it exceeds every
        # other room's gold (risk-reward contract: the boss is always the richest).
        if boss_nodes:
            max_non_boss_gold = max(
                (
                    n.metadata.get("loot", {}).get("gold", 0)
                    for n in graph.nodes
                    if "boss" not in n.tags
                ),
                default=0,
            )
            per_boss = boss_pool // len(boss_nodes)
            # Guarantee boss gold is strictly >= every other room's gold.
            guaranteed_gold = max(per_boss, max_non_boss_gold)
            for node in boss_nodes:
                items: list[dict] = []
                if rng.random() < 0.5:
                    items.append({"type": "best_item", "value": int(per_boss * 0.3)})
                if rng.random() < 0.4:
                    items.append({"type": "gem", "value": int(per_boss * 0.2)})
                loot = {"gold": guaranteed_gold, "items": items}
                node.metadata["loot"] = loot
                if loot["gold"] > 0 or loot["items"]:
                    rooms_with_loot += 1
                total_distributed += loot["gold"] + sum(
                    i.get("value", 0) for i in loot["items"]
                )

        # ── Entrance nodes get no loot ────────────────────────────────────────
        for node in graph.nodes:
            if node.node_id in entrance_node_ids:
                node.metadata["loot"] = {"gold": 0, "items": []}

        return {
            "total_distributed": total_distributed,
            "rooms_with_loot": rooms_with_loot,
        }

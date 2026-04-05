"""
RoomPurposeAgent — Assigns a gameplay purpose (role) to every room node in
the RoomGraph, using profile room-pool weights and adjacency-preference scoring.
"""

import numpy as np
from base_agent import BaseAgent
from shared_state import SharedState
from data.room_purposes import ADJACENCY_RULES
from typing import Any

# Zone-alignment hints: purposes that gain +5 when placed in combat-heavy or
# utility zones.  Zones >= 1 suit combat; zones 0-2 suit utility.
_COMBAT_PURPOSES = {
    "guard_room", "barracks", "arena", "boss_lair",
    "cell", "corridor_hub", "portal_room",
}
_UTILITY_PURPOSES = {
    "storage", "alchemy_lab", "library", "shrine", "safe_haven",
    "armory", "crypt", "secret_chamber",
}


class RoomPurposeAgent(BaseAgent):
    name = "RoomPurposeAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        graph = shared_state.room_graph
        if graph is None:
            return {"skipped": True}

        profile = params.get("profile", {})
        rng = np.random.default_rng(shared_state.config.seed + 1000)

        room_pool: dict[str, list[str]] = profile.get("room_pool", {})
        family: str = profile.get("family", "")

        # Load adjacency rules for this family (empty dict if unknown family)
        adj_rules: dict[str, dict[str, list[str]]] = ADJACENCY_RULES.get(family, {})

        count = 0

        # ── Step 1: Assign required rooms ────────────────────────────────────
        entrance = graph.entrance_node
        if entrance is not None:
            entrance.purpose = "entrance"
            count += 1

        boss = graph.boss_node
        if boss is not None:
            boss.purpose = "boss_lair"
            count += 1

        # ── Step 2: Build weighted pool for remaining rooms ───────────────────
        # common × 6, uncommon × 3, rare × 1
        weighted_pool: list[str] = []
        for purpose in room_pool.get("common", []):
            weighted_pool.extend([purpose] * 6)
        for purpose in room_pool.get("uncommon", []):
            weighted_pool.extend([purpose] * 3)
        for purpose in room_pool.get("rare", []):
            weighted_pool.append(purpose)

        # Fallback: if pool is empty, collect everything from required tier
        if not weighted_pool:
            weighted_pool = list(room_pool.get("required", ["guard_room"]))

        # ── Step 3: Score and assign each unassigned room ─────────────────────
        # Process nodes in deterministic order (by node_id) so rng draws are
        # reproducible regardless of dict insertion order.
        ordered_nodes = sorted(graph.nodes, key=lambda n: n.node_id)

        for node in ordered_nodes:
            if node.purpose is not None:
                continue  # already assigned (entrance / boss)

            neighbor_purposes = [
                graph.get_node(nid).purpose
                for nid in graph.neighbors(node.node_id)
                if graph.get_node(nid).purpose is not None
            ]

            if adj_rules and weighted_pool:
                # First select a candidate from weighted pool (respects rarity),
                # then score unique purposes to avoid bias from duplicate entries
                unique_purposes = list(dict.fromkeys(weighted_pool))
                # Build weight map: count occurrences in weighted pool
                purpose_weights = {}
                for p in weighted_pool:
                    purpose_weights[p] = purpose_weights.get(p, 0) + 1

                best_purpose = None
                best_score = None

                for purpose in unique_purposes:
                    rules = adj_rules.get(purpose, {})
                    near = rules.get("near", [])
                    far = rules.get("far", [])

                    score = 0
                    for np_str in neighbor_purposes:
                        if np_str in near:
                            score += 10
                        if np_str in far:
                            score -= 10

                    # Zone alignment bonus
                    if purpose in _COMBAT_PURPOSES and node.zone >= 1:
                        score += 5
                    if purpose in _UTILITY_PURPOSES and 0 <= node.zone <= 2:
                        score += 5

                    # Weight bonus: common purposes get slight preference
                    score += purpose_weights.get(purpose, 1) * 0.5

                    # Deterministic jitter to break ties
                    score += int(rng.integers(-3, 4))

                    if best_score is None or score > best_score:
                        best_score = score
                        best_purpose = purpose

                node.purpose = best_purpose
            else:
                # No adjacency data — pick randomly from weighted pool
                node.purpose = weighted_pool[int(rng.integers(0, len(weighted_pool)))]

            count += 1

        return {"purposes_assigned": count}

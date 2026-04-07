"""
EncounterAgent — Distributes an XP budget across rooms using a pacing curve.

Spikes at boss/high-encounter rooms, empty rooms for rhythm.
Assigns creature lists drawn from the profile's creature_table.
"""

import math
from collections import deque
from typing import Any

import numpy as np

from .base_agent import BaseAgent
from asset_manager.shared_state import SharedState


class EncounterAgent(BaseAgent):
    """Populates room_graph nodes with encounter data (XP + creature list)."""

    name = "EncounterAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        from data.game_tables import PARTY_XP_TABLE, DIFFICULTY_MULT
        from data.room_purposes import ROOM_PURPOSES

        graph = shared_state.room_graph
        if graph is None:
            return {"skipped": True}

        party_level: int = params.get("party_level", 5)
        party_size: int = params.get("party_size", 4)
        profile: dict = params.get("profile", {})

        rng = np.random.default_rng(shared_state.config.seed + 1100)

        # ── Budget calculation ────────────────────────────────────────────────
        base_xp = PARTY_XP_TABLE.get(party_level, 500) * party_size
        loot_tier = profile.get("loot_tier", "medium")
        difficulty = DIFFICULTY_MULT.get(loot_tier, 1.0)
        room_count = graph.node_count
        room_factor = math.sqrt(room_count) / math.sqrt(8)
        total_budget = int(base_xp * difficulty * room_factor)
        boss_budget = int(total_budget * 0.25)
        main_budget = total_budget - boss_budget

        # ── BFS order from entrance ───────────────────────────────────────────
        entrance = graph.entrance_node
        if entrance is not None:
            ordered_ids = self._bfs_order(graph, entrance.node_id)
            # append any nodes not reachable via BFS (disconnected components)
            seen = set(ordered_ids)
            for node in graph.nodes:
                if node.node_id not in seen:
                    ordered_ids.append(node.node_id)
        else:
            ordered_ids = [n.node_id for n in graph.nodes]

        N = len(ordered_ids)

        # ── Pacing curve allocation ───────────────────────────────────────────
        allocations: dict[str, int] = {}

        boss_node = graph.boss_node
        boss_id = boss_node.node_id if boss_node is not None else None
        entrance_id = entrance.node_id if entrance is not None else None

        for i, node_id in enumerate(ordered_ids):
            node = graph.get_node(node_id)
            is_boss = (node_id == boss_id) or ("boss" in node.tags)
            is_entrance = (node_id == entrance_id) or ("entrance" in node.tags)

            if is_boss:
                allocations[node_id] = boss_budget
                continue

            # 20% chance of empty room for pacing (not boss, not entrance)
            if not is_entrance and rng.random() < 0.2:
                allocations[node_id] = 0
                continue

            ramp = 0.05 + 0.95 * (i / max(1, N - 1))
            base_alloc = (main_budget / max(1, N)) * ramp

            purpose = getattr(node, "purpose", None) or ""
            purpose_data = ROOM_PURPOSES.get(purpose, {})
            enc_mult = purpose_data.get("encounter_mult", 1.0)

            alloc = int(base_alloc * enc_mult)
            allocations[node_id] = alloc

        # ── Creature selection ────────────────────────────────────────────────
        creature_table: dict = profile.get("creature_table", {})
        common_pool: list[tuple[str, int]] = creature_table.get("common", [])
        uncommon_pool: list[tuple[str, int]] = creature_table.get("uncommon", [])
        boss_pool: list[tuple[str, int]] = creature_table.get("boss", [])

        # Minimum XP cost of a single creature across all pools (ensures
        # rooms with any non-zero allocation can always host at least one creature).
        all_pool = common_pool + uncommon_pool + boss_pool
        if all_pool:
            min_creature_xp = min(max(1, w * 50) for _, w in all_pool)
        else:
            min_creature_xp = 1

        for node in graph.nodes:
            node_id = node.node_id
            xp_budget = allocations.get(node_id, 0)

            if xp_budget <= 0:
                node.metadata["encounter"] = {"xp": 0, "creatures": []}
                continue

            # Clamp up so at least one creature can be placed
            xp_budget = max(xp_budget, min_creature_xp)

            is_boss = (node_id == boss_id) or ("boss" in node.tags)

            if is_boss:
                pool = boss_pool if boss_pool else (uncommon_pool + common_pool)
            else:
                pool = common_pool + uncommon_pool

            creatures = self._select_creatures(pool, xp_budget, rng)
            node.metadata["encounter"] = {"xp": xp_budget, "creatures": creatures}

        # ── Summary ──────────────────────────────────────────────────────────
        total_xp = sum(
            n.metadata.get("encounter", {}).get("xp", 0) for n in graph.nodes
        )
        rooms_with_encounters = sum(
            1 for n in graph.nodes if n.metadata.get("encounter", {}).get("creatures")
        )

        return {
            "total_xp": total_xp,
            "rooms_with_encounters": rooms_with_encounters,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _bfs_order(graph, start_id: str) -> list[str]:
        """Return node IDs in BFS order from start_id."""
        visited: list[str] = []
        seen: set[str] = {start_id}
        queue: deque[str] = deque([start_id])
        while queue:
            current = queue.popleft()
            visited.append(current)
            for neighbor in graph.neighbors(current):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        return visited

    @staticmethod
    def _select_creatures(
        pool: list[tuple[str, int]],
        xp_budget: int,
        rng: np.random.Generator,
    ) -> list[tuple[str, int]]:
        """
        Greedily fill xp_budget with creatures from pool.
        Each (name, weight) maps to weight * 50 XP.
        Returns list of (creature_name, count) tuples.
        """
        if not pool:
            return []

        # Sort pool descending by weight (strongest first)
        sorted_pool = sorted(pool, key=lambda x: x[1], reverse=True)

        counts: dict[str, int] = {}
        remaining = xp_budget

        for name, weight in sorted_pool:
            xp_each = max(1, weight * 50)
            if xp_each <= remaining:
                n = max(1, remaining // xp_each)
                counts[name] = counts.get(name, 0) + n
                remaining -= n * xp_each
                if remaining <= 0:
                    break

        # Convert to sorted list for determinism
        return [(name, cnt) for name, cnt in sorted(counts.items()) if cnt > 0]

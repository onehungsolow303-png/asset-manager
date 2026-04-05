"""
TrapAgent — Places traps in rooms based on a danger map derived from room
purpose and zone depth.

Danger score combines zone depth (0.1–0.7) with purpose-based bonuses, then
scales by profile trap_density and each room's purpose-specific trap_chance.
High-danger rooms (score > 0.6) receive a trap regardless of the roll.
"""

from typing import Any

import numpy as np

from base_agent import BaseAgent
from shared_state import SharedState

# ── Trap tables per family ────────────────────────────────────────────────────
TRAP_TABLES: dict[str, dict[str, list[str]]] = {
    "underground": {
        "common":   ["pit", "spike_floor", "dart_wall"],
        "uncommon": ["poison_gas", "collapsing_ceiling"],
        "rare":     ["boulder", "teleport"],
    },
    "fortification": {
        "common":   ["arrow_slit", "portcullis", "murder_hole"],
        "uncommon": ["boiling_oil", "alarm"],
        "rare":     ["drawbridge_drop"],
    },
    "interior": {
        "common":   ["tripwire", "false_floor"],
        "uncommon": ["poison_needle", "swinging_blade"],
        "rare":     ["mimic"],
    },
    "outdoor": {
        "common":   ["snare", "camouflaged_pit"],
        "uncommon": ["rockslide"],
        "rare":     [],
    },
    "settlement": {
        "common":   ["tripwire", "false_floor"],
        "uncommon": ["alarm", "poison_needle"],
        "rare":     [],
    },
    "large_scale": {
        "common":   ["snare", "camouflaged_pit", "tripwire"],
        "uncommon": ["rockslide", "alarm"],
        "rare":     ["boulder"],
    },
}

# Rarity thresholds: 60 % common, 30 % uncommon, 10 % rare
_RARITY_THRESHOLDS = (0.60, 0.90)  # [0, 0.60) → common, [0.60, 0.90) → uncommon, [0.90, 1) → rare


class TrapAgent(BaseAgent):
    """Populates room_graph nodes with trap data driven by a danger map."""

    name = "TrapAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        from data.room_purposes import ROOM_PURPOSES

        graph = shared_state.room_graph
        if graph is None:
            return {"skipped": True}

        profile: dict = params.get("profile", {})
        trap_density: float = float(profile.get("trap_density", 0.5))
        family: str = profile.get("family", "underground")

        # Fall back to underground table for unknown families
        trap_table = TRAP_TABLES.get(family, TRAP_TABLES["underground"])

        rng = np.random.default_rng(shared_state.config.seed + 1200)

        max_zone = graph.max_zone or 1
        traps_placed = 0

        for node in graph.nodes:
            purpose: str = getattr(node, "purpose", None) or ""

            # ── Danger map ────────────────────────────────────────────────────
            danger = (node.zone / max_zone) * 0.6 + 0.1  # base range 0.1–0.7

            if purpose in ("treasure_vault", "boss_lair"):
                danger += 0.2
            if purpose in ("entrance", "safe_haven"):
                danger = 0.0  # never trap safe rooms

            danger = min(1.0, max(0.0, danger))

            # Safe rooms: skip entirely
            if danger == 0.0:
                continue

            # ── Placement roll ────────────────────────────────────────────────
            purpose_data = ROOM_PURPOSES.get(purpose, {})
            trap_chance: float = purpose_data.get("trap_chance", 0.0)

            place_trap = (
                rng.random() < trap_density * trap_chance
                or danger > 0.6
            )

            if not place_trap:
                continue

            # ── Trap type selection (60 % common, 30 % uncommon, 10 % rare) ──
            roll = rng.random()
            if roll < _RARITY_THRESHOLDS[0]:
                tier = "common"
            elif roll < _RARITY_THRESHOLDS[1]:
                tier = "uncommon"
            else:
                tier = "rare"

            options = trap_table.get(tier, [])
            # Fall back through tiers if the chosen tier is empty
            if not options:
                for fallback in ("common", "uncommon", "rare"):
                    options = trap_table.get(fallback, [])
                    if options:
                        break

            if not options:
                continue  # no traps defined for this family at all

            trap_type = options[int(rng.integers(0, len(options)))]

            # ── Damage scaling ────────────────────────────────────────────────
            base_damage = 4 + node.zone * 3

            node.metadata["trap"] = {
                "type": trap_type,
                "damage": base_damage,
                "danger_score": round(danger, 4),
            }
            traps_placed += 1

        return {"traps_placed": traps_placed}

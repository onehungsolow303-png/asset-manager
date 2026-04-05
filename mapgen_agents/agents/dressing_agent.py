"""
DressingAgent — Fills rooms with furniture and atmosphere metadata based on room purpose.

For each room node that has a purpose, the agent:
  1. Selects furniture from a purpose-matched palette (universal + purpose-specific items)
  2. Places items at random walkable positions inside the room bounds
  3. Writes atmosphere metadata (lighting, sound) onto the room node
"""

from typing import Any

import numpy as np

from base_agent import BaseAgent
from shared_state import SharedState, Entity

# ---------------------------------------------------------------------------
# Dressing palettes
# ---------------------------------------------------------------------------

DRESSING_PALETTES: dict[str, dict] = {
    "dungeon": {
        "universal": ["torch", "cobweb", "rubble", "bones", "chains"],
        "by_purpose": {
            "guard_room": ["weapon_rack", "table", "chair", "lantern", "barrel"],
            "barracks": ["bunk_bed", "footlocker", "armor_stand"],
            "armory": ["weapon_rack", "shield_display", "grindstone", "crate"],
            "storage": ["barrel", "crate", "sack", "shelf"],
            "alchemy_lab": ["cauldron", "bookshelf", "potion_shelf", "brazier"],
            "library": ["bookshelf", "desk", "candelabra", "scroll_rack", "reading_chair"],
            "shrine": ["altar", "candles", "statue", "offering_bowl"],
            "crypt": ["sarcophagus", "coffin", "urn", "eternal_flame"],
            "boss_lair": ["throne", "trophy_pile", "banner", "brazier", "cage"],
            "treasure_vault": ["chest", "gold_pile", "gem_display", "pedestal"],
            "cell": ["shackles", "straw_pile", "bucket"],
            "entrance": ["gate", "guard_alcove"],
        },
    },
    # Other palettes fall back to "dungeon"
}

ATMOSPHERE: dict[str, dict] = {
    "guard_room": {"lighting": "torchlit", "sound": "armor_clink"},
    "crypt": {"lighting": "dim", "sound": "dripping"},
    "alchemy_lab": {"lighting": "green_glow", "sound": "bubbling"},
    "boss_lair": {"lighting": "dramatic", "sound": "ominous_hum"},
    "library": {"lighting": "candlelit", "sound": "page_rustle"},
    "shrine": {"lighting": "warm_glow", "sound": "chanting"},
    "cell": {"lighting": "dark", "sound": "chains_rattle"},
    "treasure_vault": {"lighting": "glittering", "sound": "silence"},
    "entrance": {"lighting": "torchlit", "sound": "wind"},
    "storage": {"lighting": "dim", "sound": "silence"},
    "barracks": {"lighting": "torchlit", "sound": "snoring"},
    "armory": {"lighting": "torchlit", "sound": "metal_clink"},
}

_DEFAULT_ATMOSPHERE = {"lighting": "dim", "sound": "silence"}

# ---------------------------------------------------------------------------
# Item count scaling by room area
# ---------------------------------------------------------------------------

def _item_count(area: int, rng: np.random.Generator) -> int:
    """Return how many dressing items a room of `area` cells should receive."""
    if area < 400:
        return int(rng.integers(2, 4))       # 2-3
    elif area <= 1200:
        return int(rng.integers(4, 7))       # 4-6
    else:
        return int(rng.integers(6, 11))      # 6-10


class DressingAgent(BaseAgent):
    """Places purpose-matched furniture and sets atmosphere metadata on room nodes."""

    name = "DressingAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        graph = shared_state.room_graph
        if graph is None:
            return {"skipped": True}

        rng = np.random.default_rng(shared_state.config.seed + 1400)

        profile: dict = params.get("profile", {})
        palette_key: str = profile.get("dressing_palette", "dungeon")
        palette: dict = DRESSING_PALETTES.get(palette_key, DRESSING_PALETTES["dungeon"])

        universal_items: list[str] = palette.get("universal", [])
        by_purpose: dict[str, list[str]] = palette.get("by_purpose", {})

        walkability = shared_state.walkability
        map_h, map_w = walkability.shape

        items_placed = 0
        rooms_dressed = 0

        for node in graph.nodes:
            purpose = getattr(node, "purpose", None)
            if not purpose:
                continue
            if node.position is None or node.size is None:
                continue

            rx, ry = node.position
            rw, rh = node.size
            area = rw * rh

            # ── Determine how many items to place ────────────────────────────
            total_count = _item_count(area, rng)

            # Split: 1-2 universal, rest from purpose list
            universal_count = min(int(rng.integers(1, 3)), total_count)  # 1 or 2
            purpose_count = max(total_count - universal_count, 0)

            # ── Build item sequences ──────────────────────────────────────────
            purpose_specific: list[str] = by_purpose.get(purpose, [])

            items_to_place: list[str] = []

            # Pick universal items (with replacement if list is short)
            if universal_items:
                indices = rng.integers(0, len(universal_items), size=universal_count)
                items_to_place.extend(universal_items[i] for i in indices)

            # Pick purpose items (with replacement if list is short)
            if purpose_specific and purpose_count > 0:
                indices = rng.integers(0, len(purpose_specific), size=purpose_count)
                items_to_place.extend(purpose_specific[i] for i in indices)
            elif purpose_count > 0 and universal_items:
                # Fallback: extra universal items
                indices = rng.integers(0, len(universal_items), size=purpose_count)
                items_to_place.extend(universal_items[i] for i in indices)

            # ── Place each item ───────────────────────────────────────────────
            for item_name in items_to_place:
                placed = False
                for _ in range(10):
                    ix = int(rng.integers(rx, rx + rw))
                    iy = int(rng.integers(ry, ry + rh))
                    # Clamp to map bounds
                    if ix < 0 or ix >= map_w or iy < 0 or iy >= map_h:
                        continue
                    if not walkability[iy, ix]:
                        continue
                    entity = Entity(
                        entity_type="dressing",
                        position=(ix, iy),
                        variant=item_name,
                        metadata={"room": node.node_id},
                    )
                    shared_state.entities.append(entity)
                    items_placed += 1
                    placed = True
                    break
                # If no walkable cell found after 10 tries, skip this item

            # ── Set atmosphere metadata ───────────────────────────────────────
            node.metadata["atmosphere"] = ATMOSPHERE.get(purpose, _DEFAULT_ATMOSPHERE).copy()
            rooms_dressed += 1

        return {"items_placed": items_placed, "rooms_dressed": rooms_dressed}

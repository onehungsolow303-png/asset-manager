"""
SpawnAgent -- Places player, enemy, and NPC spawn points on the map.

Reads walkability data from SharedState, places spawns on valid tiles,
and writes SpawnPoint objects to shared_state.spawns.

Enemy stats follow d20 conventions: HP, AC, STR, DEX, CON, SPD, ATK (dice string).
"""

import numpy as np
from base_agent import BaseAgent
from shared_state import SharedState, SpawnPoint
from typing import Any


# ---------------------------------------------------------------------------
# Enemy templates -- escalating d20-style stat blocks
# ---------------------------------------------------------------------------
ENEMY_TEMPLATES = {
    "rat": {
        "hp": 4, "ac": 10, "str": 3, "dex": 14, "con": 8, "spd": 6,
        "atk": "1d4", "ai_behavior": "chase",
    },
    "wolf": {
        "hp": 11, "ac": 13, "str": 12, "dex": 15, "con": 12, "spd": 8,
        "atk": "1d6+2", "ai_behavior": "chase",
    },
    "bandit": {
        "hp": 16, "ac": 14, "str": 13, "dex": 12, "con": 12, "spd": 6,
        "atk": "1d8+1", "ai_behavior": "patrol",
    },
    "skeleton": {
        "hp": 13, "ac": 13, "str": 10, "dex": 14, "con": 10, "spd": 6,
        "atk": "1d6+2", "ai_behavior": "guard",
    },
    "goblin": {
        "hp": 10, "ac": 15, "str": 8, "dex": 16, "con": 10, "spd": 6,
        "atk": "1d6+2", "ai_behavior": "patrol",
    },
    "zombie": {
        "hp": 22, "ac": 8, "str": 14, "dex": 6, "con": 16, "spd": 4,
        "atk": "1d6+1", "ai_behavior": "chase",
    },
    "guard": {
        "hp": 20, "ac": 16, "str": 14, "dex": 12, "con": 14, "spd": 6,
        "atk": "1d8+2", "ai_behavior": "guard",
    },
    "orc": {
        "hp": 30, "ac": 14, "str": 18, "dex": 10, "con": 16, "spd": 6,
        "atk": "1d12+3", "ai_behavior": "chase",
    },
    "ogre": {
        "hp": 50, "ac": 12, "str": 20, "dex": 8, "con": 18, "spd": 4,
        "atk": "2d8+4", "ai_behavior": "guard",
    },
    "troll": {
        "hp": 60, "ac": 15, "str": 20, "dex": 12, "con": 20, "spd": 6,
        "atk": "2d6+5", "ai_behavior": "patrol",
    },
}

# ---------------------------------------------------------------------------
# Map type -> enemy config
# Each entry: list of (enemy_type, count) tuples, plus npc_count for gold tokens
# ---------------------------------------------------------------------------
MAP_TYPE_ENEMIES: dict[str, dict] = {
    # -- Settlements --
    "village":         {"enemies": [("rat", 2), ("wolf", 1)],                      "npcs": 4},
    "town":            {"enemies": [("rat", 2), ("bandit", 2)],                    "npcs": 6},
    "city":            {"enemies": [("bandit", 3), ("guard", 2)],                  "npcs": 8},

    # -- Fortifications --
    "castle":          {"enemies": [("guard", 4), ("orc", 2)],                     "npcs": 3},
    "fort":            {"enemies": [("guard", 3), ("bandit", 2)],                  "npcs": 2},
    "tower":           {"enemies": [("guard", 2), ("skeleton", 2)],                "npcs": 1},

    # -- Underground / Interior --
    "dungeon":         {"enemies": [("skeleton", 3), ("goblin", 2), ("orc", 1)],   "npcs": 0},
    "cave":            {"enemies": [("rat", 3), ("wolf", 2), ("goblin", 1)],       "npcs": 0},
    "mine":            {"enemies": [("goblin", 3), ("rat", 2)],                    "npcs": 0},
    "maze":            {"enemies": [("skeleton", 2), ("zombie", 2)],               "npcs": 0},
    "treasure_room":   {"enemies": [("orc", 2), ("ogre", 1)],                      "npcs": 0},

    # -- Religious / Burial --
    "crypt":           {"enemies": [("skeleton", 4), ("zombie", 2)],               "npcs": 0},
    "tomb":            {"enemies": [("skeleton", 3), ("zombie", 2)],               "npcs": 0},
    "graveyard":       {"enemies": [("zombie", 3), ("skeleton", 2)],               "npcs": 0},
    "temple":          {"enemies": [("guard", 2), ("skeleton", 1)],                "npcs": 2},
    "church":          {"enemies": [("guard", 1)],                                 "npcs": 3},

    # -- Commercial / Industrial --
    "shop":            {"enemies": [("rat", 1), ("bandit", 1)],                    "npcs": 3},
    "shopping_center": {"enemies": [("bandit", 2), ("rat", 2)],                   "npcs": 5},
    "factory":         {"enemies": [("bandit", 2), ("guard", 1)],                 "npcs": 2},

    # -- Interior / Social --
    "tavern":          {"enemies": [("bandit", 2), ("rat", 1)],                    "npcs": 4},
    "prison":          {"enemies": [("guard", 3), ("bandit", 2)],                 "npcs": 1},
    "library":         {"enemies": [("skeleton", 1)],                              "npcs": 2},
    "throne_room":     {"enemies": [("guard", 4), ("orc", 1)],                    "npcs": 2},

    # -- Waterfront --
    "dock":            {"enemies": [("bandit", 2), ("rat", 2)],                    "npcs": 3},
    "harbor":          {"enemies": [("bandit", 3), ("guard", 1)],                 "npcs": 4},

    # -- Combat / Encounter --
    "arena":           {"enemies": [("orc", 2), ("ogre", 1), ("troll", 1)],       "npcs": 0},

    # -- Field / Outdoor --
    "wilderness":      {"enemies": [("wolf", 3), ("bandit", 1)],                  "npcs": 0},
    "camp":            {"enemies": [("bandit", 2), ("wolf", 1)],                  "npcs": 2},
    "outpost":         {"enemies": [("guard", 2), ("bandit", 1)],                 "npcs": 1},
    "rest_area":       {"enemies": [("rat", 1), ("wolf", 1)],                     "npcs": 2},
    "crash_site":      {"enemies": [("bandit", 2), ("wolf", 2)],                  "npcs": 0},

    # -- Large Scale --
    "biomes":          {"enemies": [("wolf", 3), ("bandit", 2), ("orc", 1)],      "npcs": 4},
    "region":          {"enemies": [("wolf", 2), ("bandit", 3), ("orc", 1)],      "npcs": 6},
    "open_world":      {"enemies": [("wolf", 3), ("bandit", 3), ("orc", 2)],      "npcs": 6},
    "world_box":       {"enemies": [("wolf", 4), ("bandit", 3), ("orc", 2), ("troll", 1)], "npcs": 8},
}

# Default player stats
PLAYER_STATS = {
    "hp": 30, "ac": 15, "str": 16, "dex": 14, "con": 14, "spd": 6, "atk": "1d8+3",
}

# Minimum distance (in tiles) between enemies and the player spawn
ENEMY_EXCLUSION_RADIUS = 8


class SpawnAgent(BaseAgent):
    """Places player, enemy, and NPC spawn points onto the map."""

    name = "SpawnAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        rng = shared_state.rng
        map_type = params.get("map_type", shared_state.config.map_type)
        walkable = shared_state.get_walkable_positions()  # bool mask (h, w)
        h, w = walkable.shape

        # Collect all walkable (y, x) positions
        ys, xs = np.where(walkable)
        if len(ys) == 0:
            # Fallback: use entire grid if nothing is walkable
            ys, xs = np.where(np.ones((h, w), dtype=bool))

        walkable_set = set(zip(xs.tolist(), ys.tolist()))  # (x, y) set

        # ── 1. Place player near map center ──
        cx, cy = w // 2, h // 2
        player_pos = self._nearest_walkable(cx, cy, xs, ys)

        shared_state.spawns.append(SpawnPoint(
            x=player_pos[0], y=player_pos[1], z=0,
            token_type="player", name="Player",
            stats=dict(PLAYER_STATS),
            ai_behavior="static",
        ))

        # ── 2. Place enemies ──
        config = MAP_TYPE_ENEMIES.get(map_type, MAP_TYPE_ENEMIES["village"])
        enemies_placed = 0

        for enemy_type, count in config["enemies"]:
            template = ENEMY_TEMPLATES[enemy_type]
            for _ in range(count):
                pos = self._random_walkable_away_from(
                    player_pos, ENEMY_EXCLUSION_RADIUS,
                    xs, ys, rng,
                )
                if pos is None:
                    # If we can't place far enough away, place anywhere walkable
                    idx = rng.integers(0, len(xs))
                    pos = (int(xs[idx]), int(ys[idx]))

                ai = template["ai_behavior"]
                stats = {k: v for k, v in template.items() if k != "ai_behavior"}

                shared_state.spawns.append(SpawnPoint(
                    x=pos[0], y=pos[1], z=0,
                    token_type="enemy",
                    name=enemy_type.capitalize(),
                    stats=stats,
                    ai_behavior=ai,
                ))
                enemies_placed += 1

        # ── 3. Place NPCs (gold tokens) ──
        npc_count = config.get("npcs", 0)
        npcs_placed = 0
        for i in range(npc_count):
            idx = rng.integers(0, len(xs))
            pos = (int(xs[idx]), int(ys[idx]))
            shared_state.spawns.append(SpawnPoint(
                x=pos[0], y=pos[1], z=0,
                token_type="npc",
                name=f"NPC_{i+1}",
                stats={"hp": 10, "ac": 10},
                ai_behavior="static",
            ))
            npcs_placed += 1

        return {
            "player_pos": player_pos,
            "enemies_placed": enemies_placed,
            "npcs_placed": npcs_placed,
            "total_spawns": len(shared_state.spawns),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _nearest_walkable(cx: int, cy: int,
                          xs: np.ndarray, ys: np.ndarray) -> tuple[int, int]:
        """Return the walkable tile closest to (cx, cy)."""
        dists = (xs - cx) ** 2 + (ys - cy) ** 2
        idx = np.argmin(dists)
        return (int(xs[idx]), int(ys[idx]))

    @staticmethod
    def _random_walkable_away_from(
        origin: tuple[int, int], min_dist: int,
        xs: np.ndarray, ys: np.ndarray,
        rng: np.random.Generator,
        max_attempts: int = 50,
    ) -> tuple[int, int] | None:
        """Pick a random walkable tile at least min_dist from origin."""
        ox, oy = origin
        dists = np.sqrt((xs - ox) ** 2 + (ys - oy) ** 2)
        far_mask = dists >= min_dist
        far_indices = np.where(far_mask)[0]

        if len(far_indices) == 0:
            return None

        idx = rng.choice(far_indices)
        return (int(xs[idx]), int(ys[idx]))

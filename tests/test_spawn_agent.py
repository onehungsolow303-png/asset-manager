"""Tests for SpawnAgent -- player, enemy, and NPC spawn placement."""

import sys
import os
import numpy as np
import pytest

# Add mapgen_agents to path so imports resolve like agents expect.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from shared_state import SharedState, MapConfig, SpawnPoint
from agents.spawn_agent import SpawnAgent, ENEMY_TEMPLATES, MAP_TYPE_ENEMIES, ENEMY_EXCLUSION_RADIUS


def _make_state(map_type="village", width=64, height=64, seed=42):
    cfg = MapConfig(width=width, height=height, map_type=map_type, seed=seed)
    return SharedState(cfg)


# ------------------------------------------------------------------
# Player spawn
# ------------------------------------------------------------------

class TestPlayerSpawn:
    def test_player_placed(self):
        """A player spawn should always be created."""
        ss = _make_state("village")
        agent = SpawnAgent()
        agent.execute(ss, {"map_type": "village"})

        players = [s for s in ss.spawns if s.token_type == "player"]
        assert len(players) == 1
        p = players[0]
        assert p.name == "Player"
        assert p.z == 0
        assert p.stats["hp"] == 30
        assert p.stats["ac"] == 15
        assert p.stats["atk"] == "1d8+3"

    def test_player_near_center(self):
        """Player should be placed close to map center."""
        ss = _make_state("village", width=128, height=128)
        agent = SpawnAgent()
        agent.execute(ss, {"map_type": "village"})

        p = [s for s in ss.spawns if s.token_type == "player"][0]
        cx, cy = 64, 64
        dist = ((p.x - cx) ** 2 + (p.y - cy) ** 2) ** 0.5
        # Should be reasonably close (within 20 tiles of center on a clean map)
        assert dist < 20


# ------------------------------------------------------------------
# Enemy spawns
# ------------------------------------------------------------------

class TestEnemySpawns:
    def test_enemies_placed_dungeon(self):
        """Dungeon should have skeleton, goblin, and orc enemies."""
        ss = _make_state("dungeon")
        agent = SpawnAgent()
        agent.execute(ss, {"map_type": "dungeon"})

        enemies = [s for s in ss.spawns if s.token_type == "enemy"]
        config = MAP_TYPE_ENEMIES["dungeon"]
        expected_count = sum(c for _, c in config["enemies"])
        assert len(enemies) == expected_count

        enemy_names = {e.name.lower() for e in enemies}
        assert "skeleton" in enemy_names
        assert "goblin" in enemy_names

    def test_enemies_have_d20_stats(self):
        """All enemies should have hp, ac, str, dex, con, spd, atk stats."""
        ss = _make_state("dungeon")
        agent = SpawnAgent()
        agent.execute(ss, {"map_type": "dungeon"})

        enemies = [s for s in ss.spawns if s.token_type == "enemy"]
        required_keys = {"hp", "ac", "str", "dex", "con", "spd", "atk"}
        for e in enemies:
            assert required_keys.issubset(e.stats.keys()), f"{e.name} missing stats: {required_keys - e.stats.keys()}"

    def test_enemies_away_from_player(self):
        """Enemies should be at least ENEMY_EXCLUSION_RADIUS tiles from player."""
        ss = _make_state("arena", width=256, height=256)
        agent = SpawnAgent()
        agent.execute(ss, {"map_type": "arena"})

        players = [s for s in ss.spawns if s.token_type == "player"]
        enemies = [s for s in ss.spawns if s.token_type == "enemy"]
        assert len(players) == 1
        px, py = players[0].x, players[0].y

        for e in enemies:
            dist = ((e.x - px) ** 2 + (e.y - py) ** 2) ** 0.5
            # On a 256x256 fully walkable map there is plenty of room
            assert dist >= ENEMY_EXCLUSION_RADIUS, (
                f"{e.name} at ({e.x},{e.y}) is only {dist:.1f} tiles from player at ({px},{py})"
            )


# ------------------------------------------------------------------
# NPC spawns
# ------------------------------------------------------------------

class TestNPCSpawns:
    def test_npcs_placed_village(self):
        """Village should place NPCs (gold tokens)."""
        ss = _make_state("village")
        agent = SpawnAgent()
        agent.execute(ss, {"map_type": "village"})

        npcs = [s for s in ss.spawns if s.token_type == "npc"]
        expected = MAP_TYPE_ENEMIES["village"]["npcs"]
        assert len(npcs) == expected
        assert expected > 0  # village should have NPCs

    def test_no_npcs_in_dungeon(self):
        """Dungeon should have zero NPCs."""
        ss = _make_state("dungeon")
        agent = SpawnAgent()
        agent.execute(ss, {"map_type": "dungeon"})

        npcs = [s for s in ss.spawns if s.token_type == "npc"]
        assert len(npcs) == 0


# ------------------------------------------------------------------
# Walkability
# ------------------------------------------------------------------

class TestWalkability:
    def test_all_spawns_on_walkable_tiles(self):
        """Every spawn point should be on a walkable tile."""
        ss = _make_state("village", width=64, height=64)
        # Mark some tiles as non-walkable
        ss.water_mask[0:10, :] = True
        ss.structure_mask[:, 0:10] = True

        agent = SpawnAgent()
        agent.execute(ss, {"map_type": "village"})

        walkable = ss.get_walkable_positions()
        for sp in ss.spawns:
            assert walkable[sp.y, sp.x], (
                f"{sp.token_type} '{sp.name}' at ({sp.x},{sp.y}) is NOT on a walkable tile"
            )

    def test_spawns_work_with_restricted_map(self):
        """Agent should still place spawns even when most of the map is blocked."""
        ss = _make_state("dungeon", width=64, height=64)
        # Block almost everything -- leave a 10x10 patch walkable
        ss.walkability[:] = False
        ss.walkability[27:37, 27:37] = True

        agent = SpawnAgent()
        result = agent.execute(ss, {"map_type": "dungeon"})

        assert result["status"] == "completed"
        assert len(ss.spawns) > 0

        walkable = ss.get_walkable_positions()
        for sp in ss.spawns:
            assert walkable[sp.y, sp.x]


# ------------------------------------------------------------------
# Template coverage
# ------------------------------------------------------------------

class TestTemplateCoverage:
    def test_all_35_map_types_have_config(self):
        """MAP_TYPE_ENEMIES should have an entry for every expected map type."""
        expected = {
            "village", "town", "city", "castle", "fort", "tower",
            "dungeon", "cave", "mine", "maze", "treasure_room",
            "crypt", "tomb", "graveyard", "temple", "church",
            "shop", "shopping_center", "factory", "tavern", "prison",
            "library", "throne_room", "dock", "harbor", "arena",
            "wilderness", "camp", "outpost", "rest_area", "crash_site",
            "biomes", "region", "open_world", "world_box",
        }
        assert expected.issubset(MAP_TYPE_ENEMIES.keys())

    def test_all_enemy_types_in_templates(self):
        """Every enemy referenced in MAP_TYPE_ENEMIES should exist in ENEMY_TEMPLATES."""
        for map_type, config in MAP_TYPE_ENEMIES.items():
            for enemy_type, count in config["enemies"]:
                assert enemy_type in ENEMY_TEMPLATES, f"{map_type} references unknown enemy '{enemy_type}'"

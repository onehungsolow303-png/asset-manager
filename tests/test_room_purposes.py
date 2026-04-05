"""Tests for room purpose definitions and adjacency rules."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from data.room_purposes import ROOM_PURPOSES, ADJACENCY_RULES


class TestRoomPurposes:
    def test_all_purposes_have_required_keys(self):
        required = {"encounter_mult", "trap_chance", "loot_mult"}
        for name, purpose in ROOM_PURPOSES.items():
            assert required.issubset(purpose.keys()), f"{name} missing keys: {required - purpose.keys()}"

    def test_encounter_mult_non_negative(self):
        for name, purpose in ROOM_PURPOSES.items():
            assert purpose["encounter_mult"] >= 0.0, f"{name} has negative encounter_mult"

    def test_trap_chance_in_range(self):
        for name, purpose in ROOM_PURPOSES.items():
            assert 0.0 <= purpose["trap_chance"] <= 1.0, f"{name} trap_chance out of range"

    def test_loot_mult_non_negative(self):
        for name, purpose in ROOM_PURPOSES.items():
            assert purpose["loot_mult"] >= 0.0, f"{name} has negative loot_mult"

    def test_boss_lair_is_strongest(self):
        assert ROOM_PURPOSES["boss_lair"]["encounter_mult"] >= 2.0
        assert ROOM_PURPOSES["boss_lair"]["loot_mult"] >= 2.0

    def test_safe_haven_has_no_danger(self):
        assert ROOM_PURPOSES["safe_haven"]["encounter_mult"] == 0.0
        assert ROOM_PURPOSES["safe_haven"]["trap_chance"] == 0.0

    def test_minimum_purpose_count(self):
        assert len(ROOM_PURPOSES) >= 16


class TestAdjacencyRules:
    def test_underground_family_exists(self):
        assert "underground" in ADJACENCY_RULES

    def test_adjacency_has_near_and_far(self):
        for family, rules in ADJACENCY_RULES.items():
            for purpose, adj in rules.items():
                assert "near" in adj, f"{family}.{purpose} missing 'near'"
                assert "far" in adj, f"{family}.{purpose} missing 'far'"

    def test_guard_room_near_entrance(self):
        assert "entrance" in ADJACENCY_RULES["underground"]["guard_room"]["near"]

    def test_boss_lair_far_from_entrance(self):
        assert "entrance" in ADJACENCY_RULES["underground"]["boss_lair"]["far"]

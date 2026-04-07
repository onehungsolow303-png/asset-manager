"""Tests for D&D-derived game balance tables."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from data.game_tables import PARTY_XP_TABLE, TREASURE_TABLE, SIZE_ROOM_COUNTS


class TestPartyXpTable:
    def test_covers_levels_1_to_20(self):
        for level in range(1, 21):
            assert level in PARTY_XP_TABLE, f"Missing level {level}"

    def test_xp_increases_with_level(self):
        prev = 0
        for level in range(1, 21):
            assert PARTY_XP_TABLE[level] >= prev, f"Level {level} XP doesn't increase"
            prev = PARTY_XP_TABLE[level]

    def test_level_1_is_reasonable(self):
        assert 25 <= PARTY_XP_TABLE[1] <= 100


class TestTreasureTable:
    def test_covers_levels_1_to_20(self):
        for level in range(1, 21):
            assert level in TREASURE_TABLE, f"Missing level {level}"

    def test_treasure_increases_with_level(self):
        prev = 0
        for level in range(1, 21):
            assert TREASURE_TABLE[level] >= prev, f"Level {level} treasure doesn't increase"
            prev = TREASURE_TABLE[level]


class TestSizeRoomCounts:
    def test_all_sizes_present(self):
        sizes = ["small_encounter", "medium_encounter", "large_encounter", "standard", "large", "region", "open_world"]
        for size in sizes:
            assert size in SIZE_ROOM_COUNTS, f"Missing size {size}"

    def test_all_families_present(self):
        families = ["underground", "fortification", "settlement", "interior", "outdoor", "large_scale"]
        for size, counts in SIZE_ROOM_COUNTS.items():
            for family in families:
                assert family in counts, f"Missing {family} in {size}"

    def test_open_world_has_more_rooms_than_small(self):
        for family in ["underground", "fortification", "settlement"]:
            small = SIZE_ROOM_COUNTS["small_encounter"][family]
            big = SIZE_ROOM_COUNTS["open_world"][family]
            assert big > small, f"{family}: open_world should have more rooms than small_encounter"

    def test_minimum_room_count(self):
        for size, counts in SIZE_ROOM_COUNTS.items():
            for family, count in counts.items():
                assert count >= 3, f"{family}/{size} has fewer than 3 rooms"

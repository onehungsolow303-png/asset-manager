"""Tests for map type profiles and family configuration."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mapgen_agents"))

from pipeline.profiles import MAP_TYPE_PROFILES, FAMILIES, get_profile, get_family


ALL_MAP_TYPES = [
    "dungeon", "cave", "mine", "maze", "crypt", "tomb",
    "castle", "fort", "tower", "outpost",
    "village", "town", "city", "camp", "rest_area",
    "tavern", "prison", "library", "throne_room", "shop",
    "shopping_center", "factory", "temple", "church", "treasure_room",
    "wilderness", "graveyard", "dock", "arena", "crash_site",
    "biomes", "region", "open_world", "world_box",
]

REQUIRED_PROFILE_KEYS = {
    "family", "topology_preference", "size_topology_override", "room_pool",
    "creature_table", "trap_density", "loot_tier", "dressing_palette",
    "biome_override", "z_levels", "corridor_style", "door_frequency",
    "secret_room_chance",
}

ALL_FAMILIES = ["underground", "fortification", "settlement", "interior", "outdoor", "large_scale"]


class TestProfiles:
    def test_all_map_types_present(self):
        for mt in ALL_MAP_TYPES:
            assert mt in MAP_TYPE_PROFILES, f"Missing profile for {mt}"

    def test_profile_has_required_keys(self):
        for mt, profile in MAP_TYPE_PROFILES.items():
            missing = REQUIRED_PROFILE_KEYS - profile.keys()
            assert not missing, f"{mt} missing keys: {missing}"

    def test_family_is_valid(self):
        for mt, profile in MAP_TYPE_PROFILES.items():
            assert profile["family"] in ALL_FAMILIES, f"{mt} has invalid family: {profile['family']}"

    def test_topology_preference_is_list(self):
        for mt, profile in MAP_TYPE_PROFILES.items():
            assert isinstance(profile["topology_preference"], list), f"{mt} topology_preference not a list"
            assert len(profile["topology_preference"]) >= 1, f"{mt} has empty topology_preference"

    def test_room_pool_has_required(self):
        for mt, profile in MAP_TYPE_PROFILES.items():
            pool = profile["room_pool"]
            assert "required" in pool, f"{mt} room_pool missing 'required'"
            assert "common" in pool, f"{mt} room_pool missing 'common'"
            assert len(pool["required"]) >= 1, f"{mt} has no required rooms"

    def test_trap_density_in_range(self):
        for mt, profile in MAP_TYPE_PROFILES.items():
            assert 0.0 <= profile["trap_density"] <= 1.0, f"{mt} trap_density out of range"

    def test_door_frequency_in_range(self):
        for mt, profile in MAP_TYPE_PROFILES.items():
            assert 0.0 <= profile["door_frequency"] <= 1.0, f"{mt} door_frequency out of range"

    def test_secret_room_chance_in_range(self):
        for mt, profile in MAP_TYPE_PROFILES.items():
            assert 0.0 <= profile["secret_room_chance"] <= 1.0, f"{mt} secret_room_chance out of range"

    def test_loot_tier_valid(self):
        valid_tiers = {"low", "medium", "high", "legendary"}
        for mt, profile in MAP_TYPE_PROFILES.items():
            assert profile["loot_tier"] in valid_tiers, f"{mt} has invalid loot_tier"

    def test_z_levels_valid(self):
        for mt, profile in MAP_TYPE_PROFILES.items():
            z = profile["z_levels"]
            assert z["min"] >= 1, f"{mt} z_levels.min < 1"
            assert z["max"] >= z["min"], f"{mt} z_levels.max < min"


class TestGetProfile:
    def test_known_type(self):
        profile = get_profile("dungeon")
        assert profile["family"] == "underground"

    def test_unknown_type_raises(self):
        with pytest.raises(KeyError):
            get_profile("nonexistent")


class TestGetFamily:
    def test_returns_family_name(self):
        assert get_family("dungeon") == "underground"
        assert get_family("village") == "settlement"
        assert get_family("tavern") == "interior"


class TestFamilies:
    def test_all_families_defined(self):
        for family in ALL_FAMILIES:
            assert family in FAMILIES

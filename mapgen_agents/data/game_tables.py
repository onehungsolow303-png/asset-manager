"""D&D 5e-derived game balance tables for encounter and loot budgets."""

# XP threshold per player per level (D&D 5e "medium" encounter threshold).
PARTY_XP_TABLE: dict[int, int] = {
    1: 50, 2: 100, 3: 150, 4: 250, 5: 500,
    6: 600, 7: 750, 8: 900, 9: 1100, 10: 1200,
    11: 1600, 12: 2000, 13: 2200, 14: 2500, 15: 2800,
    16: 3200, 17: 3900, 18: 4200, 19: 4900, 20: 5700,
}

# Gold piece value per player per level for total dungeon treasure.
TREASURE_TABLE: dict[int, int] = {
    1: 30, 2: 60, 3: 100, 4: 175, 5: 350,
    6: 500, 7: 750, 8: 1000, 9: 1500, 10: 2000,
    11: 3000, 12: 4000, 13: 5500, 14: 7500, 15: 10000,
    16: 13000, 17: 17000, 18: 22000, 19: 28000, 20: 40000,
}

# Base room count per map size and family. Jittered +/-20% at generation time.
SIZE_ROOM_COUNTS: dict[str, dict[str, int]] = {
    "small_encounter":  {"underground": 5,  "fortification": 4,  "settlement": 4,  "interior": 4,  "outdoor": 3,  "large_scale": 6},
    "medium_encounter": {"underground": 8,  "fortification": 6,  "settlement": 6,  "interior": 6,  "outdoor": 5,  "large_scale": 10},
    "large_encounter":  {"underground": 12, "fortification": 8,  "settlement": 8,  "interior": 8,  "outdoor": 7,  "large_scale": 15},
    "standard":         {"underground": 10, "fortification": 8,  "settlement": 8,  "interior": 7,  "outdoor": 6,  "large_scale": 12},
    "large":            {"underground": 16, "fortification": 12, "settlement": 12, "interior": 10, "outdoor": 10, "large_scale": 20},
    "region":           {"underground": 20, "fortification": 15, "settlement": 15, "interior": 12, "outdoor": 12, "large_scale": 30},
    "open_world":       {"underground": 25, "fortification": 20, "settlement": 20, "interior": 15, "outdoor": 15, "large_scale": 50},
}

# Loot tier -> difficulty multiplier (used for both XP and treasure budgets)
DIFFICULTY_MULT: dict[str, float] = {
    "low": 0.6,
    "medium": 1.0,
    "high": 1.5,
    "legendary": 2.0,
}

"""Room purpose definitions with gameplay multipliers and adjacency rules."""

# Each entry: {"encounter_mult": float, "trap_chance": float, "loot_mult": float}
# encounter_mult: scales enemy encounter strength (0=none, 1=normal, 3=boss)
# trap_chance:    probability 0.0–1.0 of a trap being present
# loot_mult:      scales loot value/quantity (0=none, 1=normal, 3=jackpot)

ROOM_PURPOSES: dict[str, dict[str, float]] = {
    # ── Combat ────────────────────────────────────────────────────────────────
    "guard_room":       {"encounter_mult": 1.2, "trap_chance": 0.2, "loot_mult": 0.5},
    "barracks":         {"encounter_mult": 1.5, "trap_chance": 0.1, "loot_mult": 0.3},
    "arena":            {"encounter_mult": 2.0, "trap_chance": 0.0, "loot_mult": 0.8},
    "boss_lair":        {"encounter_mult": 3.0, "trap_chance": 0.3, "loot_mult": 2.5},

    # ── Treasure ──────────────────────────────────────────────────────────────
    "treasure_vault":   {"encounter_mult": 0.5, "trap_chance": 0.8, "loot_mult": 3.0},
    "armory":           {"encounter_mult": 0.3, "trap_chance": 0.4, "loot_mult": 2.0},

    # ── Utility ───────────────────────────────────────────────────────────────
    "storage":          {"encounter_mult": 0.2, "trap_chance": 0.1, "loot_mult": 0.4},
    "alchemy_lab":      {"encounter_mult": 0.3, "trap_chance": 0.5, "loot_mult": 1.5},
    "library":          {"encounter_mult": 0.1, "trap_chance": 0.3, "loot_mult": 1.2},

    # ── Atmospheric ───────────────────────────────────────────────────────────
    "shrine":           {"encounter_mult": 0.0, "trap_chance": 0.2, "loot_mult": 0.8},
    "crypt":            {"encounter_mult": 0.8, "trap_chance": 0.4, "loot_mult": 1.0},
    "cell":             {"encounter_mult": 0.3, "trap_chance": 0.1, "loot_mult": 0.1},
    "safe_haven":       {"encounter_mult": 0.0, "trap_chance": 0.0, "loot_mult": 0.2},

    # ── Structural ────────────────────────────────────────────────────────────
    "entrance":         {"encounter_mult": 0.3, "trap_chance": 0.1, "loot_mult": 0.0},
    "corridor_hub":     {"encounter_mult": 0.5, "trap_chance": 0.3, "loot_mult": 0.1},
    "secret_chamber":   {"encounter_mult": 0.0, "trap_chance": 0.6, "loot_mult": 2.0},
    "portal_room":      {"encounter_mult": 0.5, "trap_chance": 0.3, "loot_mult": 0.5},

    # ── Settlement ────────────────────────────────────────────────────────────
    "town_square":      {"encounter_mult": 0.0, "trap_chance": 0.0, "loot_mult": 0.0},
    "house":            {"encounter_mult": 0.1, "trap_chance": 0.0, "loot_mult": 0.2},
    "tavern":           {"encounter_mult": 0.2, "trap_chance": 0.0, "loot_mult": 0.3},
    "shop":             {"encounter_mult": 0.1, "trap_chance": 0.1, "loot_mult": 0.8},
    "farm":             {"encounter_mult": 0.1, "trap_chance": 0.0, "loot_mult": 0.1},
    "well":             {"encounter_mult": 0.0, "trap_chance": 0.0, "loot_mult": 0.0},
    "blacksmith":       {"encounter_mult": 0.1, "trap_chance": 0.0, "loot_mult": 1.0},
    "inn":              {"encounter_mult": 0.1, "trap_chance": 0.0, "loot_mult": 0.3},
    "stable":           {"encounter_mult": 0.1, "trap_chance": 0.0, "loot_mult": 0.1},
    "manor":            {"encounter_mult": 0.3, "trap_chance": 0.2, "loot_mult": 1.5},
    "hidden_cellar":    {"encounter_mult": 0.5, "trap_chance": 0.5, "loot_mult": 2.0},

    # ── Interior ──────────────────────────────────────────────────────────────
    "common_room":      {"encounter_mult": 0.2, "trap_chance": 0.0, "loot_mult": 0.2},
    "kitchen":          {"encounter_mult": 0.1, "trap_chance": 0.0, "loot_mult": 0.1},
    "bar":              {"encounter_mult": 0.2, "trap_chance": 0.0, "loot_mult": 0.3},
    "guest_room":       {"encounter_mult": 0.1, "trap_chance": 0.0, "loot_mult": 0.3},
    "cellar":           {"encounter_mult": 0.3, "trap_chance": 0.3, "loot_mult": 0.5},
    "owner_quarters":   {"encounter_mult": 0.2, "trap_chance": 0.2, "loot_mult": 0.8},
    "gambling_den":     {"encounter_mult": 0.4, "trap_chance": 0.2, "loot_mult": 1.0},
}

# Adjacency rules are soft constraints for room placement.
# "near": room types that should be spatially close (preferred neighbours)
# "far":  room types that should be spatially distant (discouraged neighbours)
# Families correspond to dungeon/map themes; only purposes relevant to that
# family need entries — missing entries are treated as unconstrained.

ADJACENCY_RULES: dict[str, dict[str, dict[str, list[str]]]] = {

    # ── Underground dungeon ───────────────────────────────────────────────────
    "underground": {
        "guard_room":     {"near": ["entrance", "treasure_vault", "boss_lair"], "far": ["safe_haven"]},
        "barracks":       {"near": ["armory", "guard_room", "storage"],         "far": ["boss_lair"]},
        "treasure_vault": {"near": ["guard_room"],                               "far": ["entrance"]},
        "boss_lair":      {"near": ["treasure_vault"],                           "far": ["entrance", "safe_haven"]},
        "safe_haven":     {"near": ["entrance"],                                 "far": ["boss_lair", "guard_room"]},
        "alchemy_lab":    {"near": ["library", "storage"],                       "far": []},
        "library":        {"near": ["alchemy_lab", "shrine"],                    "far": []},
        "shrine":         {"near": ["crypt", "library"],                         "far": ["barracks"]},
        "armory":         {"near": ["barracks", "guard_room"],                   "far": []},
        "storage":        {"near": ["barracks", "kitchen"],                      "far": []},
        "cell":           {"near": ["guard_room"],                               "far": ["treasure_vault"]},
        "entrance":       {"near": ["guard_room", "safe_haven"],                 "far": ["boss_lair"]},
    },

    # ── Fortification / castle ────────────────────────────────────────────────
    "fortification": {
        "entrance":       {"near": ["guard_room", "corridor_hub"],               "far": ["boss_lair", "treasure_vault"]},
        "guard_room":     {"near": ["entrance", "barracks", "armory"],           "far": ["shrine", "safe_haven"]},
        "barracks":       {"near": ["armory", "guard_room", "storage"],          "far": ["boss_lair", "shrine"]},
        "armory":         {"near": ["barracks", "guard_room"],                   "far": ["shrine"]},
        "boss_lair":      {"near": ["treasure_vault"],                           "far": ["entrance", "barracks"]},
        "treasure_vault": {"near": ["boss_lair", "guard_room"],                  "far": ["entrance"]},
        "storage":        {"near": ["barracks", "kitchen"],                      "far": []},
        "shrine":         {"near": ["library", "crypt"],                         "far": ["barracks", "guard_room"]},
        "library":        {"near": ["shrine", "alchemy_lab"],                    "far": []},
        "crypt":          {"near": ["shrine"],                                   "far": ["barracks", "entrance"]},
        "safe_haven":     {"near": ["shrine", "library"],                        "far": ["boss_lair", "arena"]},
        "corridor_hub":   {"near": ["entrance", "barracks"],                     "far": []},
        "arena":          {"near": ["barracks"],                                 "far": ["shrine", "library"]},
        "cell":           {"near": ["guard_room", "entrance"],                   "far": ["treasure_vault"]},
    },

    # ── Settlement / town ─────────────────────────────────────────────────────
    "settlement": {
        "town_square":    {"near": ["tavern", "shop", "blacksmith", "well"],     "far": ["hidden_cellar", "manor"]},
        "tavern":         {"near": ["town_square", "stable", "inn"],             "far": ["farm", "well"]},
        "inn":            {"near": ["tavern", "stable", "town_square"],          "far": ["farm"]},
        "shop":           {"near": ["town_square", "blacksmith"],                "far": ["farm", "stable"]},
        "blacksmith":     {"near": ["shop", "stable", "town_square"],            "far": ["inn", "manor"]},
        "stable":         {"near": ["inn", "tavern", "farm"],                    "far": ["town_square", "shop"]},
        "farm":           {"near": ["stable", "well"],                           "far": ["town_square", "tavern", "shop"]},
        "well":           {"near": ["town_square", "farm"],                      "far": []},
        "house":          {"near": ["town_square", "well"],                      "far": ["hidden_cellar"]},
        "manor":          {"near": ["town_square"],                              "far": ["farm", "stable", "blacksmith"]},
        "hidden_cellar":  {"near": ["tavern", "manor"],                          "far": ["town_square", "well"]},
    },

    # ── Interior building (tavern / inn rooms) ────────────────────────────────
    "interior": {
        "common_room":    {"near": ["bar", "kitchen", "guest_room"],             "far": ["cellar", "owner_quarters"]},
        "bar":            {"near": ["common_room", "kitchen"],                   "far": ["owner_quarters", "cellar"]},
        "kitchen":        {"near": ["bar", "common_room", "cellar"],             "far": ["guest_room", "gambling_den"]},
        "guest_room":     {"near": ["common_room"],                              "far": ["kitchen", "cellar"]},
        "cellar":         {"near": ["kitchen"],                                  "far": ["guest_room", "common_room"]},
        "owner_quarters": {"near": ["cellar"],                                   "far": ["bar", "common_room", "gambling_den"]},
        "gambling_den":   {"near": ["bar", "common_room"],                       "far": ["kitchen", "owner_quarters"]},
    },

    # ── Outdoor / wilderness ──────────────────────────────────────────────────
    "outdoor": {
        "entrance":       {"near": ["safe_haven", "corridor_hub"],               "far": ["boss_lair"]},
        "shrine":         {"near": ["crypt", "safe_haven"],                      "far": ["arena", "barracks"]},
        "crypt":          {"near": ["shrine"],                                   "far": ["entrance", "safe_haven"]},
        "safe_haven":     {"near": ["entrance", "shrine"],                       "far": ["boss_lair", "arena"]},
        "boss_lair":      {"near": [],                                           "far": ["entrance", "safe_haven", "shrine"]},
        "secret_chamber": {"near": [],                                           "far": ["entrance", "safe_haven"]},
        "corridor_hub":   {"near": ["entrance"],                                 "far": []},
        "portal_room":    {"near": ["secret_chamber"],                           "far": ["entrance"]},
        "arena":          {"near": [],                                           "far": ["shrine", "safe_haven"]},
    },

    # ── Large-scale complex (megadungeon / multi-zone) ────────────────────────
    "large_scale": {
        "entrance":       {"near": ["safe_haven", "guard_room", "corridor_hub"], "far": ["boss_lair", "secret_chamber"]},
        "corridor_hub":   {"near": ["entrance", "guard_room", "storage"],        "far": []},
        "guard_room":     {"near": ["entrance", "corridor_hub", "barracks"],     "far": ["safe_haven", "shrine"]},
        "barracks":       {"near": ["guard_room", "armory", "storage"],          "far": ["boss_lair", "shrine"]},
        "armory":         {"near": ["barracks", "guard_room"],                   "far": []},
        "storage":        {"near": ["barracks", "corridor_hub"],                 "far": []},
        "safe_haven":     {"near": ["entrance", "shrine"],                       "far": ["boss_lair", "arena", "guard_room"]},
        "shrine":         {"near": ["library", "crypt", "safe_haven"],           "far": ["barracks", "arena"]},
        "library":        {"near": ["shrine", "alchemy_lab"],                    "far": []},
        "alchemy_lab":    {"near": ["library", "storage"],                       "far": []},
        "crypt":          {"near": ["shrine"],                                   "far": ["entrance", "barracks"]},
        "cell":           {"near": ["guard_room"],                               "far": ["treasure_vault", "shrine"]},
        "treasure_vault": {"near": ["guard_room", "boss_lair"],                  "far": ["entrance", "corridor_hub"]},
        "boss_lair":      {"near": ["treasure_vault", "arena"],                  "far": ["entrance", "safe_haven", "shrine"]},
        "arena":          {"near": ["boss_lair", "barracks"],                    "far": ["shrine", "library", "safe_haven"]},
        "secret_chamber": {"near": ["portal_room"],                              "far": ["entrance", "corridor_hub"]},
        "portal_room":    {"near": ["secret_chamber", "boss_lair"],              "far": ["entrance", "safe_haven"]},
    },
}

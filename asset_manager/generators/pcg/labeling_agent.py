"""
LabelingAgent — Names locations and generates flavor text using procedural generation.
Can use LLM for richer output, but falls back to Markov chain / template system.
"""

import numpy as np
from base_agent import BaseAgent
from shared_state import SharedState, Label
from typing import Any


# Name generation components
NAME_PARTS = {
    "forest": {
        "prefix": ["Whisper", "Shadow", "Green", "Moss", "Fern", "Elder", "Oak",
                    "Willow", "Thorn", "Bramble", "Silver", "Dawn", "Misty", "Deep"],
        "suffix": ["wood", "grove", "dell", "glen", "hollow", "thicket", "reach",
                    "shade", " Falls", " Creek", " Ridge", " Clearing"],
        "settlements": ["Haven", "Rest", "Watch", "Crossing", "Lodge", "Camp",
                        "Hearth", "Refuge", "Dale", "Stead"],
    },
    "mountain": {
        "prefix": ["Iron", "Storm", "Stone", "Frost", "Eagle", "Thunder", "High",
                    "Grey", "Granite", "Cloud", "Peak", "Crag", "Anvil", "Hawk"],
        "suffix": ["peak", "crest", "summit", "spire", "pass", "cliff", " Gorge",
                    " Fortress", " Hold", " Keep"],
        "settlements": ["Fortress", "Citadel", "Hold", "Bastion", "Keep", "Tower",
                        "Stronghold", "Garrison"],
    },
    "desert": {
        "prefix": ["Sun", "Sand", "Dust", "Amber", "Scorch", "Dune", "Oasis",
                    "Mirage", "Gold", "Copper", "Ember", "Dry", "Burnt"],
        "suffix": ["drift", "waste", "reach", "expanse", " Sands", " Wastes",
                    " Oasis", " Springs", " Gulch"],
        "settlements": ["Oasis", "Haven", "Rest", "Camp", "Well", "Shade",
                        "Bazaar", "Caravan"],
    },
    "swamp": {
        "prefix": ["Murk", "Bog", "Dark", "Dank", "Rot", "Mire", "Sludge",
                    "Wither", "Gloom", "Foul", "Moss", "Marsh"],
        "suffix": ["mire", "fen", "marsh", "bog", "swamp", " Hollow", " Depths",
                    " Pools", " Moor"],
        "settlements": ["Hovel", "Shack", "Den", "Lair", "Hut", "Refuge"],
    },
    "plains": {
        "prefix": ["Wind", "Gold", "Wheat", "Sun", "Wide", "Open", "Swift",
                    "Bright", "Amber", "Green", "Far", "Long"],
        "suffix": ["field", "meadow", "prairie", "vale", "lea", " Plains",
                    " Crossing", " Road"],
        "settlements": ["Village", "Farm", "Hamlet", "Mill", "Grange", "Steading"],
    },
    "tundra": {
        "prefix": ["Frost", "Ice", "Snow", "White", "Bitter", "Frozen", "Pale",
                    "Winter", "Crystal", "Cold", "North", "Bleak"],
        "suffix": ["waste", "reach", "tundra", "expanse", " Glacier", " Drift",
                    " Fields", " Wastes"],
        "settlements": ["Shelter", "Camp", "Lodge", "Outpost", "Station"],
    },
    "volcanic": {
        "prefix": ["Ember", "Ash", "Flame", "Magma", "Cinder", "Scorch", "Inferno",
                    "Obsidian", "Char", "Blaze", "Sulphur"],
        "suffix": ["pit", "caldera", "vent", "crater", " Wastes", " Fields",
                    " Furnace", " Forge"],
        "settlements": ["Forge", "Crucible", "Furnace", "Kiln", "Smelter"],
    },
    "cave": {
        "prefix": ["Deep", "Dark", "Echo", "Crystal", "Shadow", "Glimmer", "Under",
                    "Blind", "Silent", "Dread", "Pale"],
        "suffix": ["cavern", "grotto", "depths", "hollow", " Caves", " Tunnels",
                    " Chambers", " Abyss"],
        "settlements": ["Den", "Lair", "Camp", "Nest", "Warren"],
    },
    "dungeon": {
        "prefix": ["Dread", "Lost", "Cursed", "Forgotten", "Ancient", "Sealed",
                    "Shadow", "Blood", "Iron", "Bone", "Dark"],
        "suffix": ["keep", "vault", "tomb", "crypt", "dungeon", " Cells",
                    " Chambers", " Halls", " Pits"],
        "settlements": ["Chamber", "Sanctum", "Throne Room", "Crypt", "Vault"],
    },
    "castle": {
        "prefix": ["Crown", "Royal", "Iron", "Stone", "Golden", "Silver",
                    "Noble", "High", "Grand", "Warden", "Shield", "Regal"],
        "suffix": ["keep", "hold", "citadel", "bastion", "stronghold",
                    " Castle", " Fortress", " Palace", " Court"],
        "settlements": ["Keep", "Throne Room", "Great Hall", "Chapel",
                        "Armory", "Barracks", "Tower", "Dungeon"],
    },
    "fort": {
        "prefix": ["Stern", "Iron", "Oak", "Hardy", "Valor", "Guard",
                    "Shield", "Watch", "Bulwark", "Rampart"],
        "suffix": ["guard", "wall", "post", "gate", " Fort", " Garrison",
                    " Stockade", " Redoubt"],
        "settlements": ["Barracks", "Armory", "Gatehouse", "Mess Hall",
                        "Watchtower", "Storage"],
    },
    "tower": {
        "prefix": ["Arcane", "Star", "Moon", "Crystal", "Winding", "Ivory",
                    "Obsidian", "Sage", "Storm", "Twilight", "Celestial"],
        "suffix": ["spire", "pinnacle", "tower", "apex", " Tower",
                    " Spire", " Sanctum", " Observatory"],
        "settlements": ["Study", "Library", "Laboratory", "Observatory",
                        "Sanctum", "Chamber"],
    },
    "mine": {
        "prefix": ["Deep", "Dark", "Gold", "Iron", "Crystal", "Copper",
                    "Silver", "Hollow", "Echo", "Lost", "Rich"],
        "suffix": ["shaft", "vein", "dig", "tunnel", " Mine", " Shaft",
                    " Pit", " Excavation", " Depths"],
        "settlements": ["Cart Station", "Ore Chamber", "Tool Room",
                        "Shaft Entrance", "Deposit", "Collapse"],
    },
    "maze": {
        "prefix": ["Twisted", "Winding", "Lost", "Endless", "Shifting",
                    "Bewildering", "Tangled", "Hidden", "Blind", "Serpent"],
        "suffix": ["ways", "path", "turn", "passage", " Maze", " Labyrinth",
                    " Corridors", " Passages"],
        "settlements": ["Dead End", "Junction", "Center", "Passage",
                        "Alcove", "Turning Point"],
    },
    "arena": {
        "prefix": ["Blood", "Glory", "Thunder", "Steel", "Champion",
                    "Crimson", "Roaring", "Savage", "Trial", "Valor"],
        "suffix": ["pit", "ring", "ground", "circle", " Arena", " Coliseum",
                    " Ring", " Grounds"],
        "settlements": ["Center Ring", "Fighter's Gate", "Spectator Stand",
                        "Champion's Pit", "Holding Cell"],
    },
    "crash_site": {
        "prefix": ["Fallen", "Broken", "Shattered", "Twisted", "Burning",
                    "Scarred", "Impact", "Wreck", "Ruin", "Scorch"],
        "suffix": ["site", "wreck", "ruin", "crater", " Crater",
                    " Wreckage", " Debris Field", " Impact Zone"],
        "settlements": ["Main Wreckage", "Debris Field", "Cargo Scatter",
                        "Scorched Earth", "Salvage Point"],
    },
    "treasure_room": {
        "prefix": ["Golden", "Jeweled", "Ancient", "Forbidden", "Royal",
                    "Dragon", "Cursed", "Gilded", "Radiant", "Priceless"],
        "suffix": ["hoard", "vault", "treasury", "cache", " Vault",
                    " Treasury", " Trove", " Hoard"],
        "settlements": ["Main Vault", "Gem Display", "Gold Chamber",
                        "Trophy Hall", "Chest Alcove", "Crown Room"],
    },
    "rest_area": {
        "prefix": ["Quiet", "Warm", "Safe", "Weary", "Gentle", "Calm",
                    "Traveler", "Ember", "Peace", "Shelter"],
        "suffix": ["rest", "camp", "haven", "refuge", " Camp", " Rest",
                    " Haven", " Shelter"],
        "settlements": ["Campfire", "Bedroll", "Water Source",
                        "Lookout Point", "Supply Cache"],
    },
    "crypt": {
        "prefix": ["Bone", "Silent", "Dark", "Hollow", "Ashen", "Pale",
                    "Forsaken", "Withered", "Cold", "Ancient"],
        "suffix": ["crypt", "vault", "tomb", "ossuary", " Crypt",
                    " Vault", " Sepulcher", " Catacomb"],
        "settlements": ["Burial Chamber", "Sarcophagus Room", "Ossuary",
                        "Sealed Door", "Bone Alcove"],
    },
    "tomb": {
        "prefix": ["Eternal", "Sealed", "Lost", "Cursed", "Sacred", "Royal",
                    "Forgotten", "Ancient", "Hidden", "Grand"],
        "suffix": ["tomb", "rest", "sepulcher", "crypt", " Tomb",
                    " Mausoleum", " Burial", " Resting Place"],
        "settlements": ["Burial Hall", "Guardian Chamber", "Offering Room",
                        "Sealed Passage", "Treasure Alcove"],
    },
    "graveyard": {
        "prefix": ["Silent", "Misty", "Forgotten", "Hallowed", "Weeping",
                    "Dark", "Moonlit", "Raven", "Eternal", "Solemn"],
        "suffix": ["yard", "rest", "field", "ground", " Graveyard",
                    " Cemetery", " Burial Ground", " Memorial"],
        "settlements": ["Chapel", "Mausoleum", "Gate", "Caretaker Hut",
                        "Memorial Stone", "Crypt Entrance"],
    },
    "dock": {
        "prefix": ["Harbor", "Tide", "Salt", "Wave", "Storm", "Anchor",
                    "Pearl", "Coral", "Fisher", "Sailor"],
        "suffix": ["port", "dock", "wharf", "harbor", " Dock", " Port",
                    " Pier", " Landing", " Marina"],
        "settlements": ["Warehouse", "Harbor Master", "Fish Market",
                        "Bait Shop", "Pier", "Dry Dock"],
    },
    "factory": {
        "prefix": ["Iron", "Steam", "Cog", "Hammer", "Forge", "Steel",
                    "Copper", "Brass", "Smoke", "Industry"],
        "suffix": ["works", "mill", "forge", "foundry", " Factory",
                    " Works", " Foundry", " Mill"],
        "settlements": ["Main Floor", "Furnace Room", "Loading Bay",
                        "Office", "Assembly Hall", "Storage Silo"],
    },
    "shop": {
        "prefix": ["Lucky", "Golden", "Silver", "Old", "Fine", "Grand",
                    "Honest", "Wise", "Merry", "Swift"],
        "suffix": ["shop", "store", "emporium", "market", " Shop",
                    " Store", " Goods", " Trading Post"],
        "settlements": ["Counter", "Storage Room", "Display",
                        "Shop Front", "Back Room"],
    },
    "shopping_center": {
        "prefix": ["Grand", "Central", "Royal", "Market", "Trading",
                    "Merchant", "Golden", "Bazaar", "Fair", "Commerce"],
        "suffix": ["market", "bazaar", "square", "row", " Market",
                    " Bazaar", " Square", " Exchange"],
        "settlements": ["General Store", "Potion Shop", "Armorer",
                        "Jeweler", "Tailor", "Blacksmith", "Tavern"],
    },
    "temple": {
        "prefix": ["Sacred", "Divine", "Holy", "Celestial", "Ancient",
                    "Blessed", "Radiant", "Eternal", "Hallowed", "Mystic"],
        "suffix": ["temple", "sanctum", "shrine", "altar", " Temple",
                    " Sanctum", " Shrine", " Cathedral"],
        "settlements": ["Inner Sanctum", "Prayer Hall", "Altar Room",
                        "Meditation Chamber", "Relic Room", "Clergy Quarters"],
    },
    "church": {
        "prefix": ["Saint", "Holy", "Blessed", "Divine", "Grace",
                    "Faith", "Light", "Dawn", "Peace", "Haven"],
        "suffix": ["church", "chapel", "cathedral", "parish", " Church",
                    " Chapel", " Parish", " Cathedral"],
        "settlements": ["Nave", "Altar", "Vestry", "Bell Tower",
                        "Chapel", "Crypt"],
    },
    "biomes": {
        "prefix": ["Ever", "Wild", "Vast", "Living", "Primal", "Ancient",
                    "Shifting", "Verdant", "Boundless", "Untamed"],
        "suffix": ["lands", "reach", "expanse", "wilds", " Lands",
                    " Reach", " Expanse", " Frontier", " Territories"],
        "settlements": ["Forest Region", "Desert Zone", "Tundra Waste",
                        "Volcanic Ridge", "Swamp Basin", "Mountain Range",
                        "Plains", "Coastal Region"],
    },
    "jungle": {
        "prefix": ["Vine", "Canopy", "Emerald", "Feral", "Serpent", "Monsoon",
                    "Orchid", "Primal", "Tiger", "Parrot", "Thorn", "Tangled"],
        "suffix": ["jungle", "wilds", "thicket", "canopy", " Jungle",
                    " Rainforest", " Basin", " Depths", " Undergrowth"],
        "settlements": ["Treehouse", "Clearing", "Ruins", "Camp",
                        "Temple Ruin", "Waterfall Camp"],
    },
    "underwater": {
        "prefix": ["Coral", "Abyssal", "Tidal", "Pearl", "Deep", "Sunken",
                    "Brine", "Kelp", "Leviathan", "Azure", "Shell", "Drift"],
        "suffix": ["reef", "trench", "depths", "grotto", " Reef",
                    " Abyss", " Shallows", " Depths", " Lagoon"],
        "settlements": ["Coral Palace", "Sunken Temple", "Grotto",
                        "Shell Cavern", "Kelp Garden", "Tidal Pool"],
    },
    "sky": {
        "prefix": ["Cloud", "Zephyr", "Aether", "Nimbus", "Wind", "Storm",
                    "Celestial", "Floating", "Drift", "Azure", "Gale", "Soaring"],
        "suffix": ["peak", "drift", "isle", "haven", " Spire",
                    " Island", " Citadel", " Reach", " Aerie"],
        "settlements": ["Sky Dock", "Cloud Temple", "Wind Shrine",
                        "Floating Market", "Aerie", "Crystal Platform"],
    },
    "tavern": {
        "prefix": ["Jolly", "Golden", "Stumbling", "Hearty", "Copper",
                    "Rusty", "Warm", "Merry", "Lucky", "Old"],
        "suffix": ["tankard", "flagon", "barrel", "hearth", " Tavern",
                    " Inn", " Pub", " Alehouse"],
        "settlements": ["Bar", "Kitchen", "Cellar", "Guest Room",
                        "Common Room", "Storage"],
    },
    "prison": {
        "prefix": ["Iron", "Stone", "Dark", "Cold", "Grim", "Bleak",
                    "Chain", "Lock", "Warden", "Hollow", "Doom"],
        "suffix": ["cell", "block", "ward", "gate", " Prison",
                    " Dungeon", " Cells", " Stockade"],
        "settlements": ["Guard Room", "Cell Block", "Warden Office",
                        "Interrogation Room", "Armory", "Courtyard"],
    },
    "library": {
        "prefix": ["Ancient", "Dusty", "Sage", "Arcane", "Gilded",
                    "Forbidden", "Silent", "Grand", "Scholar", "Tome"],
        "suffix": ["stacks", "archive", "vault", "collection", " Library",
                    " Archive", " Repository", " Athenaeum"],
        "settlements": ["Reading Hall", "Restricted Section", "Map Room",
                        "Scroll Archive", "Study", "Catalogue"],
    },
    "harbor": {
        "prefix": ["Storm", "Tide", "Salt", "Anchor", "Sail", "Wave",
                    "Harbor", "Beacon", "Pearl", "Coral", "Fisher"],
        "suffix": ["port", "harbor", "dock", "wharf", " Harbor",
                    " Port", " Bay", " Landing", " Cove"],
        "settlements": ["Lighthouse", "Shipyard", "Fish Market",
                        "Harbor Master", "Warehouse", "Dry Dock", "Pier"],
    },
    "throne_room": {
        "prefix": ["Royal", "Golden", "Sovereign", "Imperial", "Grand",
                    "Regal", "Crown", "Noble", "Majestic", "Gilded"],
        "suffix": ["throne", "court", "hall", "seat", " Throne",
                    " Court", " Hall", " Chamber"],
        "settlements": ["Throne Dais", "Audience Hall", "Antechamber",
                        "Royal Guard Post", "Gallery", "Advisory Chamber"],
    },
}

# Flavor text templates
FLAVOR_TEMPLATES = {
    "settlement": [
        "A {adj} {type} nestled {prep} the {feature}.",
        "Known for its {quality}, this {type} has stood for generations.",
        "Travelers speak of the {adj} {type} with {emotion}.",
    ],
    "water_feature": [
        "The waters here run {adj} and {quality}.",
        "Local legends claim the {type} is {legend}.",
        "A {adj} {type} that feeds the surrounding land.",
    ],
    "landmark": [
        "A {adj} formation that towers above the {feature}.",
        "Said to be {legend}, this {type} draws visitors from afar.",
        "The {adj} {type} marks the boundary of the territory.",
    ],
}

ADJECTIVES = ["ancient", "weathered", "majestic", "humble", "mystical",
              "forgotten", "sacred", "crumbling", "storied", "lonely",
              "peaceful", "ominous", "windswept", "sun-dappled", "shadowed"]

EMOTIONS = ["reverence", "caution", "wonder", "dread", "fondness", "nostalgia"]

LEGENDS = ["cursed by an old witch", "blessed by the forest spirits",
           "home to a sleeping dragon", "built on ancient ruins",
           "guarded by unseen forces", "older than memory itself"]


class LabelingAgent(BaseAgent):
    name = "LabelingAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        style = params.get("style", "fantasy")
        lore_depth = params.get("lore_depth", "medium")
        biome = shared_state.config.biome

        rng = np.random.default_rng(shared_state.config.seed + 800)
        parts = NAME_PARTS.get(biome, NAME_PARTS["forest"])

        labels_created = 0

        # Label buildings/structures
        for entity in shared_state.entities:
            if entity.entity_type in ("building", "room"):
                name = self._generate_name(parts, entity, rng)
                entity.metadata["name"] = name

                shared_state.labels.append(Label(
                    text=name,
                    position=entity.position,
                    category="settlement",
                    font_size=max(8, shared_state.config.width // 60),
                    color="#2c1810",
                ))
                labels_created += 1

        # Label water features
        for path in shared_state.paths:
            if path.path_type == "river" and path.waypoints:
                mid = path.waypoints[len(path.waypoints) // 2]
                name = f"{rng.choice(parts['prefix'])} {rng.choice(['River', 'Creek', 'Stream', 'Brook'])}"
                shared_state.labels.append(Label(
                    text=name,
                    position=mid,
                    category="water_feature",
                    font_size=max(10, shared_state.config.width // 50),
                    color="#1a4a6e",
                ))
                labels_created += 1

        # Generate map title
        map_name = f"The {rng.choice(parts['prefix'])}{rng.choice(parts['suffix'])}"
        shared_state.labels.append(Label(
            text=map_name,
            position=(shared_state.config.width // 2, 15),
            category="title",
            font_size=max(14, shared_state.config.width // 30),
            color="#1a0a00",
        ))
        shared_state.metadata["map_name"] = map_name
        labels_created += 1

        return {
            "labels_created": labels_created,
            "map_name": map_name,
            "style": style,
        }

    def _generate_name(self, parts: dict, entity, rng) -> str:
        """Generate a name for a structure entity."""
        if entity.entity_type == "building":
            base = entity.metadata.get("name", entity.variant.title())
            # Sometimes prefix with a fantasy name
            if rng.random() < 0.6:
                prefix = rng.choice(parts["prefix"])
                return f"The {prefix} {base}"
            return base
        elif entity.entity_type == "room":
            prefix = rng.choice(parts["prefix"])
            suffix = rng.choice(["Chamber", "Hall", "Room", "Sanctum", "Vault"])
            return f"{prefix} {suffix}"
        return rng.choice(parts["prefix"]) + rng.choice(parts["suffix"])

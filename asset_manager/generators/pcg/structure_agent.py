"""
StructureAgent — Places buildings, walls, dungeon rooms, mazes, mines, and other structures.
Uses BSP for dungeons, recursive backtracker for mazes, tunnel carving for mines,
and rule-based placement for villages/cities/forts/castles.
"""

import numpy as np
from base_agent import BaseAgent
from shared_state import SharedState, Entity, Transition
from typing import Any


# Building templates: (width, height, color_rgb, name_prefix)
BUILDING_TEMPLATES = {
    "village": [
        (20, 15, (120, 90, 60), "House"),
        (25, 20, (100, 80, 50), "Tavern"),
        (15, 15, (130, 100, 70), "Shop"),
        (30, 25, (90, 70, 45), "Inn"),
        (12, 10, (110, 85, 55), "Cottage"),
        (18, 14, (105, 82, 52), "Workshop"),
    ],
    "town": [
        (22, 16, (115, 88, 58), "House"),
        (28, 22, (98, 78, 48), "Tavern"),
        (18, 15, (125, 98, 68), "Market Stall"),
        (30, 25, (88, 68, 42), "Inn"),
        (20, 18, (108, 85, 55), "Smithy"),
        (25, 20, (100, 82, 52), "Stable"),
        (15, 12, (118, 92, 62), "Well House"),
        (32, 24, (92, 72, 48), "Town Hall"),
    ],
    "city": [
        (30, 25, (100, 90, 75), "Manor"),
        (20, 15, (110, 95, 70), "House"),
        (25, 20, (95, 85, 65), "Guild Hall"),
        (15, 15, (105, 90, 68), "Shop"),
        (35, 30, (85, 75, 55), "Keep"),
        (20, 18, (100, 88, 66), "Barracks"),
        (22, 16, (108, 92, 70), "Temple"),
        (18, 14, (112, 96, 72), "Warehouse"),
    ],
    "castle": [
        (60, 50, (80, 75, 65), "Great Hall"),
        (25, 25, (75, 70, 60), "Tower"),
        (30, 20, (85, 78, 68), "Barracks"),
        (20, 15, (90, 82, 72), "Armory"),
        (35, 25, (78, 72, 62), "Throne Room"),
        (18, 18, (82, 76, 66), "Chapel"),
        (15, 12, (88, 80, 70), "Dungeon Entrance"),
        (25, 20, (72, 68, 58), "Kitchen"),
    ],
    "fort": [
        (30, 25, (90, 82, 68), "Main Hall"),
        (20, 20, (85, 78, 64), "Watchtower"),
        (18, 15, (95, 86, 72), "Barracks"),
        (15, 12, (88, 80, 66), "Armory"),
        (12, 10, (92, 84, 70), "Storage"),
        (22, 18, (82, 74, 60), "Gate House"),
    ],
    "tower": [
        (30, 30, (85, 80, 70), "Main Tower"),
        (12, 12, (90, 84, 74), "Turret"),
        (15, 10, (80, 75, 65), "Bridge Room"),
        (18, 15, (88, 82, 72), "Study"),
        (20, 20, (82, 76, 66), "Observatory"),
    ],
    "camp": [
        (10, 10, (140, 120, 80), "Tent"),
        (12, 8, (135, 115, 75), "Supply Tent"),
        (8, 8, (145, 125, 85), "Bedroll"),
        (15, 12, (130, 110, 70), "Command Tent"),
    ],
    "outpost": [
        (20, 20, (100, 90, 70), "Watchtower"),
        (15, 12, (110, 95, 72), "Barracks"),
        (12, 10, (105, 90, 68), "Storage"),
        (25, 20, (95, 82, 62), "Palisade Gate"),
    ],
    "crash_site": [
        (30, 20, (70, 65, 60), "Wreckage Hull"),
        (15, 12, (80, 72, 65), "Debris Field"),
        (10, 8, (75, 68, 62), "Cargo Scatter"),
        (20, 15, (65, 60, 55), "Impact Crater"),
        (8, 8, (90, 82, 75), "Salvage Pile"),
    ],
    "treasure_room": [
        (45, 35, (100, 85, 50), "Vault"),
        (20, 20, (110, 95, 55), "Treasure Pile"),
        (15, 15, (90, 78, 45), "Chest Alcove"),
        (25, 20, (95, 82, 48), "Trophy Hall"),
        (12, 10, (105, 90, 52), "Gem Display"),
    ],
    "rest_area": [
        (12, 10, (140, 125, 90), "Campfire"),
        (10, 8, (135, 118, 82), "Bedroll"),
        (8, 8, (130, 115, 80), "Pack"),
        (14, 10, (125, 110, 78), "Log Bench"),
    ],
    "dungeon": [
        (40, 30, (70, 65, 58), "Chamber"),
        (25, 25, (75, 68, 60), "Room"),
        (50, 40, (65, 60, 52), "Great Hall"),
        (20, 20, (72, 66, 58), "Cell"),
    ],
    "mine": [
        (30, 25, (65, 58, 48), "Shaft Room"),
        (20, 15, (70, 62, 52), "Vein Chamber"),
        (15, 12, (60, 55, 45), "Tool Storage"),
        (25, 20, (68, 60, 50), "Cart Station"),
        (35, 30, (62, 56, 46), "Ore Deposit"),
    ],
    "maze": [],  # Mazes use procedural generation, not templates
    "arena": [
        (20, 20, (100, 90, 70), "Pillar"),
        (15, 15, (110, 95, 72), "Barrier"),
        (10, 10, (95, 85, 65), "Platform"),
        (25, 8, (105, 92, 68), "Wall Segment"),
    ],
    "crypt": [
        (35, 30, (55, 50, 45), "Burial Chamber"),
        (20, 20, (60, 55, 48), "Sarcophagus Room"),
        (25, 15, (50, 45, 40), "Ossuary"),
        (15, 12, (58, 52, 46), "Antechamber"),
        (30, 25, (52, 48, 42), "Catacombs"),
    ],
    "tomb": [
        (50, 40, (60, 55, 48), "Main Burial Hall"),
        (30, 25, (55, 50, 42), "Sarcophagus Chamber"),
        (20, 18, (65, 58, 50), "Offering Room"),
        (25, 20, (50, 45, 38), "Sealed Passage"),
        (35, 30, (58, 52, 45), "Guardian Chamber"),
        (15, 12, (62, 56, 48), "Treasure Alcove"),
    ],
    "graveyard": [
        (8, 4, (140, 135, 125), "Headstone"),
        (12, 8, (130, 125, 115), "Grave Plot"),
        (20, 15, (80, 75, 65), "Mausoleum"),
        (15, 12, (100, 92, 80), "Crypt Entrance"),
        (25, 20, (75, 70, 60), "Chapel"),
    ],
    "dock": [
        (40, 10, (110, 85, 50), "Pier"),
        (30, 25, (100, 80, 55), "Warehouse"),
        (20, 15, (115, 90, 60), "Harbor Master"),
        (25, 20, (105, 82, 52), "Fish Market"),
        (15, 12, (120, 95, 65), "Bait Shop"),
        (35, 15, (95, 75, 48), "Dock Platform"),
    ],
    "factory": [
        (50, 40, (90, 85, 80), "Main Factory"),
        (30, 25, (85, 80, 75), "Assembly Hall"),
        (20, 18, (95, 88, 82), "Storage Silo"),
        (25, 20, (80, 75, 70), "Furnace Room"),
        (15, 12, (100, 92, 85), "Office"),
        (35, 30, (88, 82, 76), "Loading Bay"),
    ],
    "shop": [
        (20, 15, (125, 100, 70), "Shop Front"),
        (15, 12, (120, 95, 65), "Counter"),
        (12, 10, (115, 90, 60), "Storage Room"),
        (18, 14, (130, 105, 75), "Display Area"),
    ],
    "shopping_center": [
        (25, 20, (125, 100, 70), "General Store"),
        (20, 18, (120, 95, 65), "Potion Shop"),
        (22, 16, (130, 105, 75), "Armorer"),
        (18, 15, (115, 92, 62), "Jeweler"),
        (20, 18, (110, 88, 58), "Tailor"),
        (28, 22, (105, 85, 55), "Tavern"),
        (25, 20, (100, 82, 52), "Blacksmith"),
    ],
    "temple": [
        (60, 45, (150, 145, 135), "Main Sanctum"),
        (30, 25, (140, 135, 125), "Prayer Hall"),
        (20, 20, (145, 140, 130), "Altar Room"),
        (25, 18, (135, 130, 120), "Meditation Chamber"),
        (15, 12, (155, 148, 138), "Relic Room"),
        (35, 25, (130, 125, 115), "Clergy Quarters"),
    ],
    "church": [
        (40, 30, (145, 140, 130), "Nave"),
        (20, 15, (150, 145, 135), "Altar"),
        (15, 12, (140, 135, 125), "Vestry"),
        (25, 20, (135, 130, 120), "Bell Tower Base"),
        (18, 15, (148, 142, 132), "Chapel"),
    ],
}

# Floor configs: list of (z_offset, floor_label) per structure type
FLOOR_CONFIGS = {
    "village": [(1, "roof")],
    "town": [(1, "roof")],
    "city": [(1, "upper"), (2, "roof")],
    "castle": [(-1, "dungeon"), (-2, "vault"), (1, "upper_hall"), (2, "battlements")],
    "fort": [(1, "upper"), (2, "roof")],
    "tower": [(1, "floor2"), (2, "floor3"), (3, "top")],
    "dungeon": [(-1, "level1"), (-2, "level2")],
    "cave": [(-1, "depths")],
    "mine": [(-1, "shaft1"), (-2, "shaft2")],
    "temple": [(-1, "crypt"), (1, "belfry")],
    "church": [(-1, "crypt"), (1, "belfry")],
    "tavern": [(1, "rooms")],
    "prison": [(-1, "cells")],
    "library": [(1, "upper_stacks")],
    "throne_room": [(1, "gallery")],
    "crypt": [(-1, "deep_crypt"), (-2, "ossuary")],
    "tomb": [(-1, "burial_chamber"), (-2, "sealed_vault")],
}


class StructureAgent(BaseAgent):
    name = "StructureAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        # RoomGraph-based placement takes priority when requested
        if params.get("use_room_graph") and shared_state.room_graph is not None:
            return self._place_rooms_from_graph(shared_state, params)

        structure_type = params.get("type", shared_state.config.map_type)
        building_count = params.get("building_count", 8)

        # Route to specialized generators
        if structure_type == "dungeon":
            return self._generate_dungeon_rooms(shared_state, params)
        elif structure_type == "maze":
            return self._generate_maze(shared_state, params)
        elif structure_type == "mine":
            return self._generate_mine(shared_state, params)
        elif structure_type == "castle":
            return self._generate_castle(shared_state, params)
        elif structure_type == "fort":
            return self._generate_fort(shared_state, params)
        elif structure_type == "tower":
            return self._generate_tower(shared_state, params)
        elif structure_type == "arena":
            return self._generate_arena(shared_state, params)
        elif structure_type == "crash_site":
            return self._generate_crash_site(shared_state, params)
        elif structure_type == "treasure_room":
            return self._generate_treasure_room(shared_state, params)
        elif structure_type == "crypt":
            return self._generate_crypt(shared_state, params)
        elif structure_type == "tomb":
            return self._generate_tomb(shared_state, params)
        elif structure_type == "graveyard":
            return self._generate_graveyard(shared_state, params)
        elif structure_type == "dock":
            return self._generate_dock(shared_state, params)
        elif structure_type == "factory":
            return self._generate_factory(shared_state, params)
        elif structure_type == "temple":
            return self._generate_temple(shared_state, params)
        elif structure_type == "church":
            return self._generate_church(shared_state, params)
        else:
            return self._place_buildings(shared_state, structure_type, building_count)

    # ── Multi-floor generation ─────────────────────────────────────────

    def _generate_floors(self, shared_state: SharedState, x: int, y: int,
                         w: int, h: int, structure_type: str, rng) -> None:
        """Create additional z-levels for a building footprint."""
        floors = FLOOR_CONFIGS.get(structure_type, [(1, "roof")])

        # Colors
        roof_color = (140, 120, 80)
        interior_color = (160, 140, 110)
        below_color = (80, 75, 65)

        # Sort floors so we process them in order of z_offset
        for z_offset, label in sorted(floors, key=lambda f: f[0]):
            level = shared_state.add_zlevel(z_offset)

            # Pick fill color based on depth/label
            if label == "roof":
                fill_color = roof_color
            elif z_offset < 0:
                fill_color = below_color
            else:
                fill_color = interior_color

            wall_color = tuple(max(0, c - 25) for c in fill_color)

            # Fill the building footprint on this z-level
            map_h, map_w = shared_state.config.height, shared_state.config.width
            for by in range(max(0, y), min(map_h, y + h)):
                for bx in range(max(0, x), min(map_w, x + w)):
                    is_edge = (by == y or by == y + h - 1 or
                               bx == x or bx == x + w - 1)
                    level.structure_mask[by, bx] = True
                    if is_edge:
                        level.terrain_color[by, bx] = wall_color
                        level.walkability[by, bx] = False
                    else:
                        level.terrain_color[by, bx] = fill_color
                        level.walkability[by, bx] = True

            # Place stairs connecting the adjacent z-level to this one
            stair_x = x + w // 2
            stair_y = y + h // 2

            # Clamp to map bounds
            stair_x = max(0, min(stair_x, map_w - 1))
            stair_y = max(0, min(stair_y, map_h - 1))

            if z_offset > 0:
                # Going up: from the level below to this one
                from_z = z_offset - 1
                shared_state.add_transition(Transition(
                    x=stair_x, y=stair_y,
                    from_z=from_z, to_z=z_offset,
                    transition_type="stairs_up",
                ))
            else:
                # Going down: from the level above to this one
                from_z = z_offset + 1
                shared_state.add_transition(Transition(
                    x=stair_x, y=stair_y,
                    from_z=from_z, to_z=z_offset,
                    transition_type="stairs_down",
                ))

            # Make stair tile walkable on both levels
            level.walkability[stair_y, stair_x] = True
            # Also ensure stair tile is walkable on the from_z level
            if from_z in shared_state.levels:
                shared_state.levels[from_z].walkability[stair_y, stair_x] = True

    # ── Generic building placement ──────────────────────────────────────

    def _place_buildings(self, state: SharedState, stype: str, count: int) -> dict:
        """Place buildings near roads on walkable terrain."""
        rng = np.random.default_rng(state.config.seed + 500)
        h, w = state.config.height, state.config.width

        templates = BUILDING_TEMPLATES.get(stype, BUILDING_TEMPLATES["village"])

        # Prefer placement near roads
        road_proximity = np.zeros((h, w), dtype=np.float32)
        for path in state.paths:
            if path.path_type == "road":
                for px, py in path.waypoints:
                    for dy in range(-30, 31):
                        for dx in range(-30, 31):
                            nx, ny = px + dx, py + dy
                            if 0 <= nx < w and 0 <= ny < h:
                                dist = max(1, abs(dx) + abs(dy))
                                road_proximity[ny, nx] = max(
                                    road_proximity[ny, nx], 1.0 / dist)

        placed = 0
        attempts = 0
        max_attempts = count * 50

        while placed < count and attempts < max_attempts:
            attempts += 1
            template = templates[rng.integers(len(templates))]
            bw, bh, color, name_prefix = template

            # Scale buildings to map size
            bw = max(4, bw * w // 512)
            bh = max(4, bh * h // 512)

            x = rng.integers(bw, w - bw)
            y = rng.integers(bh, h - bh)

            region = state.get_walkable_positions()[y:y+bh, x:x+bw]
            water_region = state.water_mask[y:y+bh, x:x+bw]
            struct_region = state.structure_mask[y:y+bh, x:x+bw]

            if (region.all() and not water_region.any() and not struct_region.any()):
                state.structure_mask[y:y+bh, x:x+bw] = True
                state.walkability[y:y+bh, x:x+bw] = False

                wall_color = tuple(max(0, c - 20) for c in color)
                for by in range(y, y + bh):
                    for bx in range(x, x + bw):
                        if by == y or by == y + bh - 1 or bx == x or bx == x + bw - 1:
                            state.terrain_color[by, bx] = wall_color
                        else:
                            state.terrain_color[by, bx] = color

                door_x = x + bw // 2
                door_y = y + bh - 1
                if 0 <= door_x < w and 0 <= door_y < h:
                    state.terrain_color[door_y, door_x] = (60, 40, 25)
                    state.walkability[door_y, door_x] = True

                # Draw interior details for this building
                self._draw_interior(state, x, y, bw, bh, name_prefix.lower(), rng)

                state.entities.append(Entity(
                    entity_type="building",
                    position=(x, y),
                    size=(bw, bh),
                    variant=name_prefix.lower(),
                    metadata={"name": f"{name_prefix} {placed + 1}", "style": stype}
                ))

                # Generate additional floors for this building
                floor_type = name_prefix.lower() if name_prefix.lower() in FLOOR_CONFIGS else stype
                self._generate_floors(state, x, y, bw, bh, floor_type, rng)

                placed += 1

        return {
            "buildings_placed": placed,
            "structure_type": stype,
            "attempts": attempts,
        }

    # ── Dungeon rooms (BSP) ─────────────────────────────────────────────

    def _generate_dungeon_rooms(self, state: SharedState, params: dict) -> dict:
        """Use BSP to generate connected dungeon rooms."""
        rng = np.random.default_rng(state.config.seed + 600)
        h, w = state.config.height, state.config.width
        room_count = params.get("building_count", 6)

        rooms = self._place_random_rooms(state, rng, room_count,
                                          floor_color=(75, 70, 62),
                                          wall_color=(45, 40, 35),
                                          entity_variant="dungeon_room")
        corridors = self._connect_rooms_corridors(state, rooms, rng,
                                                   floor_color=(75, 70, 62),
                                                   corridor_w=3)

        # Interior details for each dungeon room
        for rx, ry, rw, rh in rooms:
            self._draw_interior(state, rx, ry, rw, rh, "dungeon_room", rng)

        return {"rooms_created": len(rooms), "corridors_created": corridors}

    # ── Maze (recursive backtracker) ────────────────────────────────────

    def _generate_maze(self, state: SharedState, params: dict) -> dict:
        """Generate a maze using recursive backtracker algorithm."""
        rng = np.random.default_rng(state.config.seed + 610)
        h, w = state.config.height, state.config.width

        wall_color = (50, 45, 38)
        path_color = (85, 80, 70)
        cell_size = params.get("cell_size", max(4, w // 64))

        # Maze grid dimensions
        maze_w = (w - 2) // cell_size
        maze_h = (h - 2) // cell_size
        if maze_w < 3: maze_w = 3
        if maze_h < 3: maze_h = 3

        # Initialize all walls
        state.walkability[:, :] = False
        state.terrain_color[:, :] = wall_color

        # Visited grid
        visited = np.zeros((maze_h, maze_w), dtype=bool)
        stack = [(0, 0)]
        visited[0, 0] = True

        def carve_cell(cx, cy):
            """Carve a cell and the passage to it."""
            px = 1 + cx * cell_size
            py = 1 + cy * cell_size
            for dy in range(cell_size - 1):
                for dx in range(cell_size - 1):
                    nx, ny = px + dx, py + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        state.walkability[ny, nx] = True
                        state.terrain_color[ny, nx] = path_color

        def carve_passage(cx1, cy1, cx2, cy2):
            """Carve passage between two adjacent cells."""
            px1 = 1 + cx1 * cell_size
            py1 = 1 + cy1 * cell_size
            px2 = 1 + cx2 * cell_size
            py2 = 1 + cy2 * cell_size
            # Carve between centers
            min_x = min(px1, px2)
            max_x = max(px1, px2) + cell_size - 1
            min_y = min(py1, py2)
            max_y = max(py1, py2) + cell_size - 1
            for ny in range(min_y, min(max_y, h)):
                for nx in range(min_x, min(max_x, w)):
                    state.walkability[ny, nx] = True
                    state.terrain_color[ny, nx] = path_color

        carve_cell(0, 0)

        # Recursive backtracker
        while stack:
            cx, cy = stack[-1]
            neighbors = []
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < maze_w and 0 <= ny < maze_h and not visited[ny, nx]:
                    neighbors.append((nx, ny))

            if neighbors:
                ncx, ncy = neighbors[rng.integers(len(neighbors))]
                visited[ncy, ncx] = True
                carve_passage(cx, cy, ncx, ncy)
                carve_cell(ncx, ncy)
                stack.append((ncx, ncy))

                state.entities.append(Entity(
                    entity_type="room",
                    position=(1 + ncx * cell_size, 1 + ncy * cell_size),
                    size=(cell_size - 1, cell_size - 1),
                    variant="maze_cell",
                    metadata={"name": f"Passage {len(state.entities) + 1}"}
                ))
            else:
                stack.pop()

        state.structure_mask = ~state.walkability

        return {
            "maze_size": f"{maze_w}x{maze_h}",
            "cells_carved": int(visited.sum()),
            "cell_size": cell_size,
        }

    # ── Mine (tunnel network) ───────────────────────────────────────────

    def _generate_mine(self, state: SharedState, params: dict) -> dict:
        """Generate a mine with main shafts and branching tunnels."""
        rng = np.random.default_rng(state.config.seed + 620)
        h, w = state.config.height, state.config.width

        wall_color = (45, 40, 32)
        tunnel_color = (70, 62, 50)
        ore_colors = [(140, 120, 40), (120, 130, 140), (100, 50, 50)]  # gold, silver, ruby
        room_count = params.get("building_count", 5)

        # Fill with walls
        state.walkability[:, :] = False
        state.terrain_color[:, :] = wall_color

        tunnel_w = max(3, w // 80)
        tunnels_created = 0

        # Main shaft: vertical down the center-ish
        cx = w // 2 + rng.integers(-w // 8, w // 8)
        for y in range(10, h - 10):
            for dx in range(-tunnel_w, tunnel_w + 1):
                nx = cx + dx + int(rng.integers(-1, 2))  # slight wobble
                if 0 <= nx < w:
                    state.walkability[y, nx] = True
                    state.terrain_color[y, nx] = tunnel_color
        tunnels_created += 1

        # Branching tunnels from main shaft
        branch_count = params.get("branch_count", 6)
        branch_points = rng.integers(30, h - 30, size=branch_count)

        for bp_y in branch_points:
            direction = rng.choice([-1, 1])
            length = rng.integers(w // 6, w // 2)
            start_x = cx

            for step in range(length):
                bx = start_x + direction * step
                # Slight vertical drift
                by = int(bp_y + rng.integers(-1, 2))
                by = max(0, min(h - 1, by))

                for dy in range(-tunnel_w // 2, tunnel_w // 2 + 1):
                    for dx in range(-tunnel_w // 2, tunnel_w // 2 + 1):
                        nx, ny = bx + dx, by + dy
                        if 0 <= nx < w and 0 <= ny < h:
                            state.walkability[ny, nx] = True
                            state.terrain_color[ny, nx] = tunnel_color
            tunnels_created += 1

        # Place ore deposit rooms
        rooms = self._place_random_rooms(state, rng, room_count,
                                          floor_color=(72, 65, 52),
                                          wall_color=wall_color,
                                          entity_variant="mine_chamber",
                                          min_room_frac=12, max_room_frac=6)

        # Interior details for mine chambers
        for rx, ry, rw, rh in rooms:
            self._draw_interior(state, rx, ry, rw, rh, "mine_chamber", rng)

        # Scatter ore veins
        ore_count = 0
        for _ in range(room_count * 3):
            ox = rng.integers(5, w - 5)
            oy = rng.integers(5, h - 5)
            if state.walkability[oy, ox]:
                ore_color = ore_colors[rng.integers(len(ore_colors))]
                r = rng.integers(2, 5)
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        nx, ny = ox + dx, oy + dy
                        if (0 <= nx < w and 0 <= ny < h and
                            dx*dx + dy*dy <= r*r and state.walkability[ny, nx]):
                            state.terrain_color[ny, nx] = ore_color
                state.entities.append(Entity(
                    entity_type="ore_vein",
                    position=(ox, oy),
                    size=(r * 2, r * 2),
                    variant="ore",
                    metadata={"name": f"Ore Vein {ore_count + 1}"}
                ))
                ore_count += 1

        state.structure_mask = ~state.walkability

        return {
            "tunnels_created": tunnels_created,
            "rooms_created": len(rooms),
            "ore_veins": ore_count,
        }

    # ── Castle (keep + walls + towers) ──────────────────────────────────

    def _generate_castle(self, state: SharedState, params: dict) -> dict:
        """Generate a castle with outer walls, corner towers, inner keep, and courtyard."""
        rng = np.random.default_rng(state.config.seed + 630)
        h, w = state.config.height, state.config.width

        wall_color = (80, 75, 65)
        floor_color = (110, 100, 85)
        tower_color = (70, 65, 55)

        wall_thick = max(3, w // 60)
        margin = max(20, w // 8)

        # Outer walls (rectangle with margin)
        self._draw_rect_walls(state, margin, margin, w - margin, h - margin,
                               wall_thick, wall_color, floor_color)

        # Corner towers
        tower_size = max(12, w // 20)
        corners = [
            (margin - tower_size // 2, margin - tower_size // 2),
            (w - margin - tower_size // 2, margin - tower_size // 2),
            (margin - tower_size // 2, h - margin - tower_size // 2),
            (w - margin - tower_size // 2, h - margin - tower_size // 2),
        ]
        for i, (tx, ty) in enumerate(corners):
            self._draw_filled_rect(state, tx, ty, tower_size, tower_size,
                                    tower_color, wall_color)
            self._draw_interior(state, max(0, tx), max(0, ty),
                                tower_size, tower_size, "castle", rng)
            state.entities.append(Entity(
                entity_type="building",
                position=(max(0, tx), max(0, ty)),
                size=(tower_size, tower_size),
                variant="tower",
                metadata={"name": f"Tower {i + 1}", "style": "castle"}
            ))

        # Gate (south wall center)
        gate_w = max(8, w // 30)
        gate_x = w // 2 - gate_w // 2
        gate_y = h - margin - wall_thick
        for gy in range(gate_y, min(h, gate_y + wall_thick + 2)):
            for gx in range(gate_x, min(w, gate_x + gate_w)):
                if 0 <= gx < w and 0 <= gy < h:
                    state.walkability[gy, gx] = True
                    state.terrain_color[gy, gx] = (60, 40, 25)
        state.entities.append(Entity(
            entity_type="building",
            position=(gate_x, gate_y),
            size=(gate_w, wall_thick + 2),
            variant="gate",
            metadata={"name": "Castle Gate", "style": "castle"}
        ))

        # Inner keep
        keep_w = max(30, w // 5)
        keep_h = max(25, h // 5)
        keep_x = w // 2 - keep_w // 2
        keep_y = h // 3 - keep_h // 2
        self._draw_filled_rect(state, keep_x, keep_y, keep_w, keep_h,
                                (90, 82, 70), wall_color)
        self._draw_interior(state, keep_x, keep_y, keep_w, keep_h, "keep", rng)
        state.entities.append(Entity(
            entity_type="building",
            position=(keep_x, keep_y),
            size=(keep_w, keep_h),
            variant="keep",
            metadata={"name": "The Keep", "style": "castle"}
        ))

        # Inner buildings from templates
        inner_placed = self._place_buildings(state, "castle",
                                              params.get("building_count", 4))

        return {
            "structure_type": "castle",
            "towers": 4,
            "inner_buildings": inner_placed.get("buildings_placed", 0),
        }

    # ── Fort (palisade + buildings) ─────────────────────────────────────

    def _generate_fort(self, state: SharedState, params: dict) -> dict:
        """Generate a fort with palisade walls and interior structures."""
        rng = np.random.default_rng(state.config.seed + 640)
        h, w = state.config.height, state.config.width

        wall_color = (85, 70, 45)  # wooden palisade
        floor_color = (120, 105, 80)

        wall_thick = max(2, w // 80)
        margin = max(30, w // 5)

        # Palisade walls
        self._draw_rect_walls(state, margin, margin, w - margin, h - margin,
                               wall_thick, wall_color, floor_color)

        # Gate
        gate_w = max(6, w // 40)
        gate_x = w // 2 - gate_w // 2
        gate_y = h - margin - wall_thick
        for gy in range(gate_y, min(h, gate_y + wall_thick + 2)):
            for gx in range(gate_x, min(w, gate_x + gate_w)):
                if 0 <= gx < w and 0 <= gy < h:
                    state.walkability[gy, gx] = True
                    state.terrain_color[gy, gx] = (100, 80, 50)

        state.entities.append(Entity(
            entity_type="building",
            position=(gate_x, gate_y),
            size=(gate_w, wall_thick + 2),
            variant="gate",
            metadata={"name": "Fort Gate", "style": "fort"}
        ))

        # Interior buildings
        inner = self._place_buildings(state, "fort", params.get("building_count", 5))

        return {
            "structure_type": "fort",
            "inner_buildings": inner.get("buildings_placed", 0),
        }

    # ── Tower (single tall structure with floors) ───────────────────────

    def _generate_tower(self, state: SharedState, params: dict) -> dict:
        """Generate a wizard/watch tower with circular footprint and rooms."""
        rng = np.random.default_rng(state.config.seed + 650)
        h, w = state.config.height, state.config.width

        wall_color = (70, 65, 58)
        floor_color = (95, 88, 78)

        cx, cy = w // 2, h // 2
        outer_r = max(20, min(w, h) // 4)
        inner_r = outer_r - max(3, outer_r // 8)

        # Draw circular tower
        for y in range(max(0, cy - outer_r), min(h, cy + outer_r)):
            for x in range(max(0, cx - outer_r), min(w, cx + outer_r)):
                dist = np.sqrt((x - cx)**2 + (y - cy)**2)
                if dist <= outer_r:
                    state.structure_mask[y, x] = True
                    if dist <= inner_r:
                        state.walkability[y, x] = True
                        state.terrain_color[y, x] = floor_color
                    else:
                        state.walkability[y, x] = False
                        state.terrain_color[y, x] = wall_color

        state.entities.append(Entity(
            entity_type="building",
            position=(cx - outer_r, cy - outer_r),
            size=(outer_r * 2, outer_r * 2),
            variant="main_tower",
            metadata={"name": "The Tower", "style": "tower"}
        ))

        # Internal dividing walls (cross pattern for rooms)
        for y in range(max(0, cy - inner_r), min(h, cy + inner_r)):
            if 0 <= cx < w:
                state.walkability[y, cx] = False
                state.terrain_color[y, cx] = wall_color
        for x in range(max(0, cx - inner_r), min(w, cx + inner_r)):
            if 0 <= cy < h:
                state.walkability[cy, x] = False
                state.terrain_color[cy, x] = wall_color

        # Doorways in dividers
        for offset in [-inner_r // 3, inner_r // 3]:
            for dy, dx in [(offset, 0), (0, offset)]:
                ny, nx = cy + dy, cx + dx
                if 0 <= nx < w and 0 <= ny < h:
                    state.walkability[ny, nx] = True
                    state.terrain_color[ny, nx] = floor_color

        # Entrance door
        door_y = cy + outer_r - 1
        if 0 <= door_y < h:
            for dx in range(-2, 3):
                nx = cx + dx
                if 0 <= nx < w:
                    state.walkability[door_y, nx] = True
                    state.terrain_color[door_y, nx] = (60, 40, 25)

        # Surrounding rooms from templates
        inner = self._place_buildings(state, "tower", params.get("building_count", 3))

        return {
            "structure_type": "tower",
            "tower_radius": outer_r,
            "surrounding_buildings": inner.get("buildings_placed", 0),
        }

    # ── Arena (circular with obstacles) ─────────────────────────────────

    def _generate_arena(self, state: SharedState, params: dict) -> dict:
        """Generate a circular arena with walls and interior obstacles."""
        rng = np.random.default_rng(state.config.seed + 660)
        h, w = state.config.height, state.config.width

        wall_color = (90, 80, 65)
        floor_color = (150, 135, 105)

        cx, cy = w // 2, h // 2
        outer_r = max(30, min(w, h) // 3)
        inner_r = outer_r - max(3, outer_r // 10)

        # Draw arena ring
        for y in range(max(0, cy - outer_r), min(h, cy + outer_r)):
            for x in range(max(0, cx - outer_r), min(w, cx + outer_r)):
                dist = np.sqrt((x - cx)**2 + (y - cy)**2)
                if dist <= outer_r:
                    state.structure_mask[y, x] = True
                    if dist <= inner_r:
                        state.walkability[y, x] = True
                        state.terrain_color[y, x] = floor_color
                    else:
                        state.walkability[y, x] = False
                        state.terrain_color[y, x] = wall_color

        state.entities.append(Entity(
            entity_type="building",
            position=(cx - outer_r, cy - outer_r),
            size=(outer_r * 2, outer_r * 2),
            variant="arena",
            metadata={"name": "The Arena", "style": "arena"}
        ))

        # Scatter obstacles inside
        obstacle_count = params.get("building_count", 6)
        placed = 0
        for _ in range(obstacle_count * 10):
            ox = cx + rng.integers(-inner_r + 10, inner_r - 10)
            oy = cy + rng.integers(-inner_r + 10, inner_r - 10)
            if np.sqrt((ox - cx)**2 + (oy - cy)**2) < inner_r - 5:
                obs_r = rng.integers(3, max(4, inner_r // 6))
                for dy in range(-obs_r, obs_r + 1):
                    for dx in range(-obs_r, obs_r + 1):
                        nx, ny = ox + dx, oy + dy
                        if (0 <= nx < w and 0 <= ny < h and
                            dx*dx + dy*dy <= obs_r*obs_r):
                            state.walkability[ny, nx] = False
                            state.terrain_color[ny, nx] = wall_color
                state.entities.append(Entity(
                    entity_type="building",
                    position=(ox - obs_r, oy - obs_r),
                    size=(obs_r * 2, obs_r * 2),
                    variant="arena_obstacle",
                    metadata={"name": f"Obstacle {placed + 1}", "style": "arena"}
                ))
                placed += 1
                if placed >= obstacle_count:
                    break

        return {"structure_type": "arena", "obstacles_placed": placed}

    # ── Crash Site (impact crater + debris) ─────────────────────────────

    def _generate_crash_site(self, state: SharedState, params: dict) -> dict:
        """Generate an impact crater with scattered debris and wreckage."""
        rng = np.random.default_rng(state.config.seed + 670)
        h, w = state.config.height, state.config.width

        crater_color = (55, 48, 40)
        scorched_color = (65, 55, 42)

        cx, cy = w // 2, h // 2
        crater_r = max(15, min(w, h) // 5)

        # Impact crater (circular depression)
        for y in range(max(0, cy - crater_r * 2), min(h, cy + crater_r * 2)):
            for x in range(max(0, cx - crater_r * 2), min(w, cx + crater_r * 2)):
                dist = np.sqrt((x - cx)**2 + (y - cy)**2)
                if dist < crater_r:
                    state.terrain_color[y, x] = crater_color
                    state.elevation[y, x] *= 0.3
                elif dist < crater_r * 1.5:
                    state.terrain_color[y, x] = scorched_color

        state.entities.append(Entity(
            entity_type="building",
            position=(cx - crater_r, cy - crater_r),
            size=(crater_r * 2, crater_r * 2),
            variant="impact_crater",
            metadata={"name": "Impact Crater", "style": "crash_site"}
        ))

        # Scatter debris from templates
        result = self._place_buildings(state, "crash_site",
                                        params.get("building_count", 5))

        return {
            "structure_type": "crash_site",
            "crater_radius": crater_r,
            "debris_placed": result.get("buildings_placed", 0),
        }

    # ── Treasure Room (vault with alcoves) ──────────────────────────────

    def _generate_treasure_room(self, state: SharedState, params: dict) -> dict:
        """Generate an ornate treasure vault with alcoves and display areas."""
        rng = np.random.default_rng(state.config.seed + 680)
        h, w = state.config.height, state.config.width

        wall_color = (60, 55, 45)
        floor_color = (100, 85, 50)  # golden floor
        pillar_color = (80, 70, 55)

        # Main vault room (centered, large)
        margin = max(20, w // 6)
        self._draw_rect_walls(state, margin, margin, w - margin, h - margin,
                               max(3, w // 60), wall_color, floor_color)

        self._draw_interior(state, margin, margin, w - margin * 2, h - margin * 2,
                            "vault", rng)
        state.entities.append(Entity(
            entity_type="room",
            position=(margin, margin),
            size=(w - margin * 2, h - margin * 2),
            variant="vault",
            metadata={"name": "The Vault", "style": "treasure_room"}
        ))

        # Pillars in a grid pattern
        pillar_spacing = max(20, (w - margin * 2) // 5)
        pillar_r = max(2, w // 80)
        for py in range(margin + pillar_spacing, h - margin, pillar_spacing):
            for px in range(margin + pillar_spacing, w - margin, pillar_spacing):
                for dy in range(-pillar_r, pillar_r + 1):
                    for dx in range(-pillar_r, pillar_r + 1):
                        nx, ny = px + dx, py + dy
                        if (0 <= nx < w and 0 <= ny < h and
                            dx*dx + dy*dy <= pillar_r*pillar_r):
                            state.walkability[ny, nx] = False
                            state.terrain_color[ny, nx] = pillar_color

        # Treasure piles from templates
        result = self._place_buildings(state, "treasure_room",
                                        params.get("building_count", 5))

        # Entrance
        gate_w = max(6, w // 30)
        for gx in range(w // 2 - gate_w // 2, w // 2 + gate_w // 2):
            gy = h - margin
            if 0 <= gx < w and 0 <= gy < h:
                state.walkability[gy, gx] = True
                state.terrain_color[gy, gx] = (60, 40, 25)

        return {
            "structure_type": "treasure_room",
            "treasure_piles": result.get("buildings_placed", 0),
        }

    # ── Crypt (underground burial chambers) ─────────────────────────────

    def _generate_crypt(self, state: SharedState, params: dict) -> dict:
        """Generate a crypt with burial chambers and narrow corridors."""
        rng = np.random.default_rng(state.config.seed + 690)
        h, w = state.config.height, state.config.width
        room_count = params.get("building_count", 6)

        wall_color = (40, 38, 32)
        floor_color = (65, 60, 52)

        # Fill with walls
        state.walkability[:, :] = False
        state.terrain_color[:, :] = wall_color

        rooms = self._place_random_rooms(state, rng, room_count,
                                          floor_color=floor_color,
                                          wall_color=wall_color,
                                          entity_variant="crypt_chamber")
        corridors = self._connect_rooms_corridors(state, rooms, rng,
                                                   floor_color=floor_color,
                                                   corridor_w=2)

        # Interior details for crypt chambers
        for rx, ry, rw, rh in rooms:
            self._draw_interior(state, rx, ry, rw, rh, "crypt_chamber", rng)

        # Place sarcophagi (small unwalkable blocks in rooms)
        sarcophagi = 0
        for rx, ry, rw, rh in rooms:
            cx, cy = rx + rw // 2, ry + rh // 2
            sr = max(2, min(rw, rh) // 6)
            for dy in range(-sr, sr + 1):
                for dx in range(-sr, sr + 1):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        state.walkability[ny, nx] = False
                        state.terrain_color[ny, nx] = (50, 45, 38)
            sarcophagi += 1

        state.structure_mask = ~state.walkability
        return {"rooms_created": len(rooms), "corridors": corridors, "sarcophagi": sarcophagi}

    # ── Tomb (sealed burial complex) ────────────────────────────────────

    def _generate_tomb(self, state: SharedState, params: dict) -> dict:
        """Generate a tomb with a main burial hall, sealed passages, and traps."""
        rng = np.random.default_rng(state.config.seed + 695)
        h, w = state.config.height, state.config.width

        wall_color = (45, 40, 35)
        floor_color = (70, 62, 52)
        accent_color = (90, 75, 40)  # gold accents

        # Fill with walls
        state.walkability[:, :] = False
        state.terrain_color[:, :] = wall_color

        # Main hall (centered, large)
        hall_w = max(40, w // 3)
        hall_h = max(30, h // 3)
        hall_x = w // 2 - hall_w // 2
        hall_y = h // 2 - hall_h // 2
        self._draw_filled_rect(state, hall_x, hall_y, hall_w, hall_h,
                                floor_color, wall_color)
        self._draw_interior(state, hall_x, hall_y, hall_w, hall_h, "burial_hall", rng)
        state.entities.append(Entity(
            entity_type="room",
            position=(hall_x, hall_y),
            size=(hall_w, hall_h),
            variant="burial_hall",
            metadata={"name": "Main Burial Hall", "style": "tomb"}
        ))

        # Side chambers branching from main hall
        room_count = params.get("building_count", 5)
        side_rooms = []
        for i in range(room_count):
            rw = rng.integers(max(10, w // 15), max(15, w // 8))
            rh = rng.integers(max(10, h // 15), max(15, h // 8))
            side = rng.choice(["left", "right", "top", "bottom"])
            if side == "left":
                rx = hall_x - rw - 2
                ry = hall_y + rng.integers(0, max(1, hall_h - rh))
            elif side == "right":
                rx = hall_x + hall_w + 2
                ry = hall_y + rng.integers(0, max(1, hall_h - rh))
            elif side == "top":
                rx = hall_x + rng.integers(0, max(1, hall_w - rw))
                ry = hall_y - rh - 2
            else:
                rx = hall_x + rng.integers(0, max(1, hall_w - rw))
                ry = hall_y + hall_h + 2

            if 0 <= rx < w - rw and 0 <= ry < h - rh:
                self._draw_filled_rect(state, rx, ry, rw, rh, floor_color, wall_color)
                self._draw_interior(state, rx, ry, rw, rh, "tomb_chamber", rng)
                side_rooms.append((rx, ry, rw, rh))
                state.entities.append(Entity(
                    entity_type="room",
                    position=(rx, ry),
                    size=(rw, rh),
                    variant="tomb_chamber",
                    metadata={"name": f"Chamber {i + 1}", "style": "tomb"}
                ))

        # Connect side rooms to main hall
        corridors = self._connect_rooms_corridors(
            state, [(hall_x, hall_y, hall_w, hall_h)] + side_rooms, rng,
            floor_color=floor_color, corridor_w=3)

        # Entrance corridor from bottom
        entrance_w = max(4, w // 40)
        for y in range(hall_y + hall_h, min(h - 5, hall_y + hall_h + h // 4)):
            for dx in range(-entrance_w // 2, entrance_w // 2 + 1):
                nx = w // 2 + dx
                if 0 <= nx < w and 0 <= y < h:
                    state.walkability[y, nx] = True
                    state.terrain_color[y, nx] = floor_color

        state.structure_mask = ~state.walkability
        return {"rooms_created": len(side_rooms) + 1, "corridors": corridors}

    # ── Graveyard (outdoor with headstones) ─────────────────────────────

    def _generate_graveyard(self, state: SharedState, params: dict) -> dict:
        """Generate an outdoor graveyard with headstones, paths, and a chapel."""
        rng = np.random.default_rng(state.config.seed + 700)
        h, w = state.config.height, state.config.width

        # Fence perimeter
        fence_color = (50, 45, 35)
        margin = max(15, w // 10)
        thick = max(1, w // 120)
        self._draw_rect_walls(state, margin, margin, w - margin, h - margin,
                               thick, fence_color, state.terrain_color[h // 2, w // 2].tolist())

        # Gate at south
        gate_w = max(6, w // 30)
        for gx in range(w // 2 - gate_w // 2, w // 2 + gate_w // 2):
            gy = h - margin
            if 0 <= gx < w and 0 <= gy < h:
                state.walkability[gy, gx] = True

        # Place headstones in rows
        headstone_color = (160, 155, 145)
        row_spacing = max(8, w // 25)
        col_spacing = max(6, w // 30)
        headstones = 0
        for ry in range(margin + row_spacing, h - margin - row_spacing, row_spacing):
            for cx in range(margin + col_spacing, w - margin - col_spacing, col_spacing):
                if rng.random() < 0.75:
                    sw, sh = max(2, w // 100), max(3, h // 80)
                    for dy in range(sh):
                        for dx in range(sw):
                            nx, ny = cx + dx, ry + dy
                            if 0 <= nx < w and 0 <= ny < h:
                                state.terrain_color[ny, nx] = headstone_color
                                state.walkability[ny, nx] = False
                                state.structure_mask[ny, nx] = True
                    headstones += 1

        # Small chapel in corner
        chapel_w = max(20, w // 8)
        chapel_h = max(15, h // 8)
        self._draw_filled_rect(state, margin + 5, margin + 5,
                                chapel_w, chapel_h, (110, 105, 95), (70, 65, 55))
        self._draw_interior(state, margin + 5, margin + 5,
                            chapel_w, chapel_h, "chapel", rng)
        state.entities.append(Entity(
            entity_type="building",
            position=(margin + 5, margin + 5),
            size=(chapel_w, chapel_h),
            variant="chapel",
            metadata={"name": "Graveyard Chapel", "style": "graveyard"}
        ))

        return {"structure_type": "graveyard", "headstones": headstones}

    # ── Dock (waterfront with piers) ────────────────────────────────────

    def _generate_dock(self, state: SharedState, params: dict) -> dict:
        """Generate a dock/harbor with piers extending into water and warehouses."""
        rng = np.random.default_rng(state.config.seed + 710)
        h, w = state.config.height, state.config.width

        wood_color = (110, 85, 50)
        plank_color = (120, 95, 58)

        # Place water on one side (south half)
        water_line = h // 2
        for y in range(water_line, h):
            for x in range(w):
                depth_ratio = (y - water_line) / max(1, h - water_line)
                state.water_mask[y, x] = True
                state.walkability[y, x] = False
                state.terrain_color[y, x] = (
                    int(40 + 20 * (1 - depth_ratio)),
                    int(90 + 40 * (1 - depth_ratio)),
                    int(150 + 30 * (1 - depth_ratio)),
                )

        # Build piers extending into water
        pier_count = rng.integers(3, 6)
        pier_spacing = w // (pier_count + 1)
        pier_width = max(4, w // 50)
        pier_length = max(20, h // 4)

        for i in range(pier_count):
            px = pier_spacing * (i + 1)
            for y in range(water_line - 5, min(h - 5, water_line + pier_length)):
                for dx in range(-pier_width // 2, pier_width // 2 + 1):
                    nx = px + dx
                    if 0 <= nx < w and 0 <= y < h:
                        state.walkability[y, nx] = True
                        state.water_mask[y, nx] = False
                        state.terrain_color[y, nx] = wood_color if (y + dx) % 3 else plank_color
                        state.structure_mask[y, nx] = True

            state.entities.append(Entity(
                entity_type="building",
                position=(px - pier_width // 2, water_line - 5),
                size=(pier_width, pier_length),
                variant="pier",
                metadata={"name": f"Pier {i + 1}", "style": "dock"}
            ))

        # Warehouses on land side
        result = self._place_buildings(state, "dock",
                                        params.get("building_count", 4))

        return {
            "structure_type": "dock",
            "piers": pier_count,
            "buildings": result.get("buildings_placed", 0),
        }

    # ── Factory (industrial complex) ────────────────────────────────────

    def _generate_factory(self, state: SharedState, params: dict) -> dict:
        """Generate an industrial factory with main building, furnaces, and loading areas."""
        rng = np.random.default_rng(state.config.seed + 720)
        h, w = state.config.height, state.config.width

        wall_color = (70, 68, 65)
        floor_color = (95, 90, 85)
        metal_color = (110, 108, 105)

        # Main factory building (centered, large)
        margin_x = max(20, w // 5)
        margin_y = max(20, h // 4)
        self._draw_rect_walls(state, margin_x, margin_y,
                               w - margin_x, h - margin_y,
                               max(3, w // 60), wall_color, floor_color)
        self._draw_interior(state, margin_x, margin_y,
                            w - margin_x * 2, h - margin_y * 2, "factory_main", rng)

        state.entities.append(Entity(
            entity_type="building",
            position=(margin_x, margin_y),
            size=(w - margin_x * 2, h - margin_y * 2),
            variant="factory_main",
            metadata={"name": "Main Factory", "style": "factory"}
        ))

        # Machinery/furnace blocks inside
        inner_w = w - margin_x * 2
        inner_h = h - margin_y * 2
        machine_count = params.get("building_count", 5)
        machines = 0
        for _ in range(machine_count * 5):
            mw = rng.integers(max(5, inner_w // 12), max(8, inner_w // 6))
            mh = rng.integers(max(5, inner_h // 12), max(8, inner_h // 6))
            mx = margin_x + rng.integers(5, max(6, inner_w - mw - 5))
            my = margin_y + rng.integers(5, max(6, inner_h - mh - 5))

            overlap = False
            for ey in range(my, min(h, my + mh)):
                for ex in range(mx, min(w, mx + mw)):
                    if not state.walkability[ey, ex]:
                        overlap = True
                        break
                if overlap:
                    break

            if not overlap:
                for ey in range(my, min(h, my + mh)):
                    for ex in range(mx, min(w, mx + mw)):
                        state.walkability[ey, ex] = False
                        state.terrain_color[ey, ex] = metal_color
                        state.structure_mask[ey, ex] = True
                state.entities.append(Entity(
                    entity_type="building",
                    position=(mx, my),
                    size=(mw, mh),
                    variant="machinery",
                    metadata={"name": f"Machine {machines + 1}", "style": "factory"}
                ))
                machines += 1
                if machines >= machine_count:
                    break

        # Loading bay entrance
        gate_w = max(10, w // 20)
        for gx in range(w // 2 - gate_w // 2, w // 2 + gate_w // 2):
            gy = h - margin_y
            if 0 <= gx < w and 0 <= gy < h:
                state.walkability[gy, gx] = True
                state.terrain_color[gy, gx] = (80, 75, 68)

        return {"structure_type": "factory", "machines": machines}

    # ── Temple (large religious structure) ───────────────────────────────

    def _generate_temple(self, state: SharedState, params: dict) -> dict:
        """Generate a grand temple with sanctum, prayer halls, and columns."""
        rng = np.random.default_rng(state.config.seed + 730)
        h, w = state.config.height, state.config.width

        wall_color = (120, 115, 105)
        floor_color = (160, 155, 145)
        pillar_color = (130, 125, 115)

        # Outer temple walls
        margin = max(15, w // 8)
        wall_thick = max(3, w // 60)
        self._draw_rect_walls(state, margin, margin, w - margin, h - margin,
                               wall_thick, wall_color, floor_color)

        state.entities.append(Entity(
            entity_type="building",
            position=(margin, margin),
            size=(w - margin * 2, h - margin * 2),
            variant="temple_main",
            metadata={"name": "The Temple", "style": "temple"}
        ))

        # Columns along the nave
        col_spacing = max(15, (w - margin * 2) // 8)
        col_r = max(2, w // 100)
        for cx in [margin + col_spacing, w - margin - col_spacing]:
            for cy in range(margin + col_spacing, h - margin, col_spacing):
                for dy in range(-col_r, col_r + 1):
                    for dx in range(-col_r, col_r + 1):
                        nx, ny = cx + dx, cy + dy
                        if (0 <= nx < w and 0 <= ny < h and
                            dx*dx + dy*dy <= col_r*col_r):
                            state.walkability[ny, nx] = False
                            state.terrain_color[ny, nx] = pillar_color

        # Inner sanctum at the far end
        sanctum_w = max(25, (w - margin * 2) // 3)
        sanctum_h = max(20, (h - margin * 2) // 4)
        sanctum_x = w // 2 - sanctum_w // 2
        sanctum_y = margin + wall_thick + 5
        self._draw_filled_rect(state, sanctum_x, sanctum_y,
                                sanctum_w, sanctum_h, (170, 165, 150), wall_color)
        self._draw_interior(state, sanctum_x, sanctum_y,
                            sanctum_w, sanctum_h, "temple", rng)
        state.entities.append(Entity(
            entity_type="room",
            position=(sanctum_x, sanctum_y),
            size=(sanctum_w, sanctum_h),
            variant="sanctum",
            metadata={"name": "Inner Sanctum", "style": "temple"}
        ))

        # Altar in center of sanctum
        altar_r = max(2, sanctum_w // 8)
        acx = sanctum_x + sanctum_w // 2
        acy = sanctum_y + sanctum_h // 2
        for dy in range(-altar_r, altar_r + 1):
            for dx in range(-altar_r, altar_r + 1):
                nx, ny = acx + dx, acy + dy
                if 0 <= nx < w and 0 <= ny < h:
                    state.walkability[ny, nx] = False
                    state.terrain_color[ny, nx] = (180, 170, 140)

        # Entrance
        gate_w = max(8, w // 25)
        for gx in range(w // 2 - gate_w // 2, w // 2 + gate_w // 2):
            gy = h - margin
            if 0 <= gx < w and 0 <= gy < h:
                state.walkability[gy, gx] = True
                state.terrain_color[gy, gx] = (140, 130, 115)

        return {"structure_type": "temple"}

    # ── Church (smaller religious building) ──────────────────────────────

    def _generate_church(self, state: SharedState, params: dict) -> dict:
        """Generate a church with nave, altar, and bell tower."""
        rng = np.random.default_rng(state.config.seed + 740)
        h, w = state.config.height, state.config.width

        wall_color = (110, 105, 95)
        floor_color = (150, 145, 135)

        # Main nave (rectangular, centered)
        nave_w = max(30, w // 3)
        nave_h = max(40, h // 2)
        nave_x = w // 2 - nave_w // 2
        nave_y = h // 2 - nave_h // 3
        wall_thick = max(2, w // 80)
        self._draw_rect_walls(state, nave_x, nave_y,
                               nave_x + nave_w, nave_y + nave_h,
                               wall_thick, wall_color, floor_color)
        self._draw_interior(state, nave_x, nave_y, nave_w, nave_h, "nave", rng)

        state.entities.append(Entity(
            entity_type="building",
            position=(nave_x, nave_y),
            size=(nave_w, nave_h),
            variant="nave",
            metadata={"name": "Church Nave", "style": "church"}
        ))

        # Altar area at the top of the nave
        altar_w = max(10, nave_w // 3)
        altar_h = max(5, nave_h // 8)
        altar_x = nave_x + nave_w // 2 - altar_w // 2
        altar_y = nave_y + wall_thick + 3
        for ay in range(altar_y, min(h, altar_y + altar_h)):
            for ax in range(altar_x, min(w, altar_x + altar_w)):
                if 0 <= ax < w and 0 <= ay < h:
                    state.walkability[ay, ax] = False
                    state.terrain_color[ay, ax] = (170, 160, 140)
                    state.structure_mask[ay, ax] = True

        state.entities.append(Entity(
            entity_type="building",
            position=(altar_x, altar_y),
            size=(altar_w, altar_h),
            variant="altar",
            metadata={"name": "Altar", "style": "church"}
        ))

        # Bell tower (square, attached to top-left)
        tower_size = max(12, nave_w // 4)
        tower_x = nave_x - tower_size + wall_thick
        tower_y = nave_y
        if tower_x >= 0:
            self._draw_filled_rect(state, tower_x, tower_y,
                                    tower_size, tower_size, floor_color, wall_color)
            state.entities.append(Entity(
                entity_type="building",
                position=(tower_x, tower_y),
                size=(tower_size, tower_size),
                variant="bell_tower",
                metadata={"name": "Bell Tower", "style": "church"}
            ))

        # Entrance door
        gate_w = max(4, nave_w // 6)
        for gx in range(nave_x + nave_w // 2 - gate_w // 2,
                        nave_x + nave_w // 2 + gate_w // 2):
            gy = nave_y + nave_h - 1
            if 0 <= gx < w and 0 <= gy < h:
                state.walkability[gy, gx] = True
                state.terrain_color[gy, gx] = (80, 55, 30)

        # Place pews (small obstacles in rows)
        pew_start_y = nave_y + wall_thick + altar_h + 10
        pew_spacing = max(5, nave_h // 10)
        for py in range(pew_start_y, nave_y + nave_h - 10, pew_spacing):
            for side in [-1, 1]:
                px = nave_x + nave_w // 2 + side * (nave_w // 5)
                pw = max(3, nave_w // 6)
                for dx in range(pw):
                    nx = px + dx - pw // 2
                    if nave_x + wall_thick < nx < nave_x + nave_w - wall_thick and 0 <= py < h:
                        state.terrain_color[py, nx] = (100, 75, 45)

        return {"structure_type": "church"}

    # ── Interior detail rendering ─────────────────────────────────────────

    def _draw_interior(self, state, x, y, w, h, structure_type, rng):
        """Draw interior details onto terrain_color within a building footprint.

        Called after a building rectangle is placed. Draws small decorative
        elements (furniture, floor patterns, etc.) appropriate to the
        structure_type. All drawing is clipped to the map bounds and stays
        inside the (x, y, w, h) footprint (excluding the 1px border wall).
        """
        map_h, map_w = state.config.height, state.config.width

        # Interior bounds (skip 1-px border walls)
        ix, iy = x + 1, y + 1
        iw, ih = w - 2, h - 2
        if iw < 3 or ih < 3:
            return  # too small for details

        tc = state.terrain_color  # alias for brevity

        # Clamp helper
        def clamp(val, lo, hi):
            return max(lo, min(hi - 1, val))

        # Safe single-pixel set
        def px(py, px_x, color):
            if 0 <= px_x < map_w and 0 <= py < map_h:
                tc[py, px_x] = color

        # Safe horizontal line
        def hline(py, x0, x1, color):
            py = int(py)
            if py < 0 or py >= map_h:
                return
            x0, x1 = int(max(0, x0)), int(min(map_w, x1))
            if x0 < x1:
                tc[py, x0:x1] = color

        # Safe vertical line
        def vline(px_x, y0, y1, color):
            px_x = int(px_x)
            if px_x < 0 or px_x >= map_w:
                return
            y0, y1 = int(max(0, y0)), int(min(map_h, y1))
            if y0 < y1:
                tc[y0:y1, px_x] = color

        # Safe filled rect
        def frect(ry, rx, rh, rw, color):
            ry0, rx0 = int(max(0, ry)), int(max(0, rx))
            ry1, rx1 = int(min(map_h, ry + rh)), int(min(map_w, rx + rw))
            if ry0 < ry1 and rx0 < rx1:
                tc[ry0:ry1, rx0:rx1] = color

        stype = structure_type.lower()

        # ── Village / Town / City buildings ─────────────────────────
        if stype in ("village", "town", "city", "house", "cottage", "shop",
                     "inn", "workshop", "manor", "guild hall", "warehouse",
                     "market stall", "smithy", "stable", "well house",
                     "town hall", "barracks", "shop front", "counter",
                     "storage room", "display area", "general store",
                     "potion shop", "armorer", "jeweler", "tailor",
                     "blacksmith", "shopping_center", "shop", "outpost",
                     "watchtower", "storage", "palisade gate",
                     "rest_area", "campfire", "bedroll", "pack",
                     "log bench"):
            # Lighter interior floor (already placed), add 2px darker border
            base = tc[clamp(iy + 1, 0, map_h), clamp(ix + 1, 0, map_w)]
            dark_wall = tuple(max(0, int(c) - 30) for c in base)
            # Top/bottom inner wall lines
            hline(iy, ix, ix + iw, dark_wall)
            hline(iy + 1, ix, ix + iw, dark_wall)
            hline(iy + ih - 1, ix, ix + iw, dark_wall)
            hline(iy + ih - 2, ix, ix + iw, dark_wall)
            # Left/right inner wall lines
            vline(ix, iy, iy + ih, dark_wall)
            vline(ix + 1, iy, iy + ih, dark_wall)
            vline(ix + iw - 1, iy, iy + ih, dark_wall)
            vline(ix + iw - 2, iy, iy + ih, dark_wall)
            # Lighter floor center
            floor_light = tuple(min(255, int(c) + 12) for c in base)
            frect(iy + 2, ix + 2, ih - 4, iw - 4, floor_light)
            # Doorway (small dark square on south side)
            door_cx = ix + iw // 2
            frect(iy + ih - 2, door_cx - 1, 2, 3, (60, 40, 25))
            # Furniture dots (1-2 tiny colored squares)
            if iw > 6 and ih > 6:
                # Table (brown)
                tx = ix + 3 + rng.integers(0, max(1, iw - 7))
                ty = iy + 3 + rng.integers(0, max(1, ih - 7))
                frect(ty, tx, 2, 2, (90, 60, 30))
                # Bed (blue-ish)
                if iw > 8 and ih > 8:
                    bx = ix + iw - 5 - rng.integers(0, max(1, iw // 4))
                    by = iy + 3 + rng.integers(0, max(1, ih // 4))
                    frect(by, bx, 2, 3, (70, 70, 110))

        # ── Tavern ──────────────────────────────────────────────────
        elif stype in ("tavern",):
            base = tc[clamp(iy + 2, 0, map_h), clamp(ix + 2, 0, map_w)]
            dark_wall = tuple(max(0, int(c) - 25) for c in base)
            hline(iy, ix, ix + iw, dark_wall)
            hline(iy + ih - 1, ix, ix + iw, dark_wall)
            vline(ix, iy, iy + ih, dark_wall)
            vline(ix + iw - 1, iy, iy + ih, dark_wall)
            # Bar counter (dark brown horizontal line across mid-height)
            bar_y = iy + ih // 3
            hline(bar_y, ix + 2, ix + iw - 2, (55, 35, 18))
            hline(bar_y + 1, ix + 2, ix + iw - 2, (55, 35, 18))
            # Tables (small brown squares)
            for _ in range(min(3, max(1, iw * ih // 80))):
                tx = ix + 3 + rng.integers(0, max(1, iw - 6))
                ty = bar_y + 3 + rng.integers(0, max(1, iy + ih - bar_y - 6))
                frect(ty, tx, 2, 2, (80, 55, 28))
            # Fireplace (orange/red square in top-left corner)
            frect(iy + 1, ix + 1, 3, 3, (180, 80, 30))
            px(iy + 2, ix + 2, (220, 120, 40))  # bright center

        # ── Dungeon rooms ───────────────────────────────────────────
        elif stype in ("dungeon", "dungeon_room", "chamber", "room",
                       "great hall", "cell"):
            # Stone floor checkerboard pattern
            dark_stone = (65, 60, 52)
            light_stone = (78, 72, 63)
            for dy in range(2, ih - 2):
                for dx in range(2, iw - 2):
                    cy, cx = iy + dy, ix + dx
                    if 0 <= cx < map_w and 0 <= cy < map_h:
                        if (dx + dy) % 4 < 2:
                            tc[cy, cx] = dark_stone
                        else:
                            tc[cy, cx] = light_stone
            # Darker walls (2px border inside)
            wall_dark = (40, 36, 30)
            hline(iy, ix, ix + iw, wall_dark)
            hline(iy + 1, ix, ix + iw, wall_dark)
            hline(iy + ih - 1, ix, ix + iw, wall_dark)
            hline(iy + ih - 2, ix, ix + iw, wall_dark)
            vline(ix, iy, iy + ih, wall_dark)
            vline(ix + 1, iy, iy + ih, wall_dark)
            vline(ix + iw - 1, iy, iy + ih, wall_dark)
            vline(ix + iw - 2, iy, iy + ih, wall_dark)

        # ── Castle / Fort ───────────────────────────────────────────
        elif stype in ("castle", "fort", "keep", "great hall_castle",
                       "throne room", "armory", "kitchen",
                       "main hall", "gate house", "gate"):
            # Thick walls (3-4px)
            wall_c = (65, 60, 50)
            for t in range(min(4, max(2, iw // 6))):
                hline(iy + t, ix, ix + iw, wall_c)
                hline(iy + ih - 1 - t, ix, ix + iw, wall_c)
                vline(ix + t, iy, iy + ih, wall_c)
                vline(ix + iw - 1 - t, iy, iy + ih, wall_c)
            # Lighter courtyard interior
            court = (130, 120, 100)
            thick = min(4, max(2, iw // 6))
            frect(iy + thick, ix + thick, ih - thick * 2, iw - thick * 2, court)
            # Corner towers (small darker circles at corners)
            tr = max(2, min(iw, ih) // 8)
            tower_c = (55, 50, 42)
            for cy_off, cx_off in [(iy + 1, ix + 1),
                                    (iy + 1, ix + iw - 2),
                                    (iy + ih - 2, ix + 1),
                                    (iy + ih - 2, ix + iw - 2)]:
                for ddy in range(-tr, tr + 1):
                    for ddx in range(-tr, tr + 1):
                        if ddx * ddx + ddy * ddy <= tr * tr:
                            py_ = cy_off + ddy
                            px_ = cx_off + ddx
                            if (0 <= px_ < map_w and 0 <= py_ < map_h and
                                    ix <= px_ < ix + iw and iy <= py_ < iy + ih):
                                tc[py_, px_] = tower_c

        # ── Prison ──────────────────────────────────────────────────
        elif stype in ("prison", "cell_block", "dungeon entrance"):
            # Cell bars (thin dark vertical lines)
            bar_color = (35, 32, 28)
            bar_spacing = max(3, iw // 6)
            for bx in range(ix + 2, ix + iw - 2, bar_spacing):
                vline(bx, iy + 2, iy + ih - 2, bar_color)
            # Guard post (lighter area near south entrance)
            guard_w = max(3, iw // 4)
            guard_h = max(3, ih // 4)
            frect(iy + ih - guard_h - 2, ix + iw // 2 - guard_w // 2,
                  guard_h, guard_w, (100, 95, 85))

        # ── Library ─────────────────────────────────────────────────
        elif stype in ("library", "study"):
            # Shelving rows (dark brown parallel horizontal lines with gaps)
            shelf_color = (60, 40, 22)
            shelf_spacing = max(3, ih // 5)
            for sy in range(iy + 3, iy + ih - 3, shelf_spacing):
                # Leave a gap in the middle for walking
                gap_cx = ix + iw // 2
                hline(sy, ix + 2, gap_cx - 1, shelf_color)
                hline(sy, gap_cx + 2, ix + iw - 2, shelf_color)

        # ── Temple / Church ─────────────────────────────────────────
        elif stype in ("temple", "church", "chapel", "prayer hall",
                       "meditation chamber", "relic room",
                       "clergy quarters", "nave", "vestry",
                       "bell tower base", "temple_main"):
            # Central aisle (lighter path down the middle)
            aisle_w = max(2, iw // 5)
            aisle_cx = ix + iw // 2
            aisle_color = tuple(min(255, int(c) + 20)
                                for c in tc[clamp(iy + 2, 0, map_h),
                                            clamp(ix + 2, 0, map_w)])
            for ax in range(aisle_cx - aisle_w // 2, aisle_cx + aisle_w // 2 + 1):
                vline(ax, iy + 2, iy + ih - 2, aisle_color)
            # Altar (gold/yellow square at the far end)
            altar_sz = max(2, min(iw, ih) // 5)
            frect(iy + 2, aisle_cx - altar_sz // 2, altar_sz, altar_sz,
                  (190, 170, 60))

        # ── Mine tunnels ────────────────────────────────────────────
        elif stype in ("mine", "mine_chamber", "shaft room",
                       "vein chamber", "tool storage", "cart station",
                       "ore deposit"):
            # Support beams (brown lines across at regular intervals)
            beam_color = (90, 60, 30)
            beam_spacing = max(4, ih // 4)
            for by in range(iy + 2, iy + ih - 2, beam_spacing):
                hline(by, ix + 1, ix + iw - 1, beam_color)

        # ── Crypt / Tomb ────────────────────────────────────────────
        elif stype in ("crypt", "crypt_chamber", "tomb", "tomb_chamber",
                       "burial_hall", "burial chamber",
                       "sarcophagus room", "ossuary", "antechamber",
                       "catacombs", "main burial hall",
                       "sarcophagus chamber", "offering room",
                       "sealed passage", "guardian chamber",
                       "treasure alcove"):
            # Brick-pattern floor
            brick_a = (58, 52, 44)
            brick_b = (52, 46, 38)
            for dy in range(2, ih - 2):
                for dx in range(2, iw - 2):
                    cy_, cx_ = iy + dy, ix + dx
                    if 0 <= cx_ < map_w and 0 <= cy_ < map_h:
                        offset = 2 if (dy // 2) % 2 else 0
                        if (dx + offset) % 4 == 0 or dy % 2 == 0 and (dx + offset) % 4 < 1:
                            tc[cy_, cx_] = brick_a
                        else:
                            tc[cy_, cx_] = brick_b

        # ── Dock / Pier ─────────────────────────────────────────────
        elif stype in ("dock", "pier", "harbor master", "fish market",
                       "bait shop", "dock platform"):
            # Plank lines across the building
            plank_dark = (95, 72, 40)
            for dy in range(0, ih, 3):
                hline(iy + dy, ix + 1, ix + iw - 1, plank_dark)

        # ── Factory / Industrial ────────────────────────────────────
        elif stype in ("factory", "factory_main", "assembly hall",
                       "storage silo", "furnace room", "office",
                       "loading bay", "machinery"):
            # Machine outlines (small darker rectangles)
            machine_c = (75, 72, 68)
            for _ in range(min(3, max(1, iw * ih // 100))):
                mw_ = rng.integers(2, max(3, iw // 3))
                mh_ = rng.integers(2, max(3, ih // 3))
                mx_ = ix + 2 + rng.integers(0, max(1, iw - mw_ - 4))
                my_ = iy + 2 + rng.integers(0, max(1, ih - mh_ - 4))
                frect(my_, mx_, mh_, mw_, machine_c)

        # ── Crash site debris ───────────────────────────────────────
        elif stype in ("crash_site", "wreckage hull", "debris field",
                       "cargo scatter", "impact crater", "salvage pile"):
            # Scorch marks (random dark splotches)
            scorch = (50, 42, 35)
            for _ in range(min(4, max(1, iw * ih // 60))):
                sx = ix + 1 + rng.integers(0, max(1, iw - 3))
                sy = iy + 1 + rng.integers(0, max(1, ih - 3))
                frect(sy, sx, 2, 2, scorch)

        # ── Treasure room ───────────────────────────────────────────
        elif stype in ("treasure_room", "vault", "treasure pile",
                       "chest alcove", "trophy hall", "gem display"):
            # Gold/gem piles (small bright dots)
            gold = (200, 180, 50)
            gem_colors = [(180, 40, 40), (40, 180, 40), (40, 40, 200)]
            for _ in range(min(5, max(1, iw * ih // 40))):
                gx = ix + 2 + rng.integers(0, max(1, iw - 4))
                gy = iy + 2 + rng.integers(0, max(1, ih - 4))
                c = gold if rng.random() < 0.6 else gem_colors[rng.integers(3)]
                px(gy, gx, c)
                px(gy + 1, gx, c)

        # ── Arena ───────────────────────────────────────────────────
        elif stype in ("arena", "arena_obstacle", "pillar", "barrier",
                       "platform", "wall segment"):
            # Sand texture variation
            for dy in range(1, ih - 1):
                for dx in range(1, iw - 1):
                    cy_, cx_ = iy + dy, ix + dx
                    if 0 <= cx_ < map_w and 0 <= cy_ < map_h:
                        v = rng.integers(-8, 9)
                        base = tc[cy_, cx_]
                        tc[cy_, cx_] = tuple(max(0, min(255, int(c) + v))
                                             for c in base)

        # ── Graveyard chapel ────────────────────────────────────────
        elif stype in ("graveyard", "mausoleum", "crypt entrance"):
            # Simple cross-shaped window on floor
            cx_ = ix + iw // 2
            cy_ = iy + ih // 2
            cross_c = (140, 135, 120)
            vline(cx_, cy_ - 2, cy_ + 3, cross_c)
            hline(cy_, cx_ - 1, cx_ + 2, cross_c)

    # ── RoomGraph-based placement ───────────────────────────────────────

    def _place_rooms_from_graph(self, state: SharedState, params: dict) -> dict:
        """Place rooms using positions from RoomGraph. Falls back to random placement."""
        rng = np.random.default_rng(state.config.seed + 650)
        h, w = state.config.height, state.config.width
        graph = state.room_graph

        floor_color = (75, 70, 62)
        wall_color = (45, 40, 35)

        # Room size range
        min_room = max(15, w // 12)
        max_room = max(25, w // 6)

        placed = []  # list of (x, y, w, h) for collision detection
        count = graph.node_count

        # Try to place rooms in natural openings first
        openings = getattr(state, 'natural_openings', []) or []

        for node in graph.nodes:
            room_w = int(rng.integers(min_room, max_room))
            room_h = int(rng.integers(min_room, max_room))

            placed_ok = False
            rx, ry = 5, 5

            # Try natural openings first
            for ox, oy, ow, oh in openings:
                for _attempt in range(20):
                    rx = int(rng.integers(ox + 2, max(ox + 3, ox + ow - room_w - 2)))
                    ry = int(rng.integers(oy + 2, max(oy + 3, oy + oh - room_h - 2)))
                    if self._check_no_overlap(rx, ry, room_w, room_h, placed, w, h):
                        placed_ok = True
                        break
                if placed_ok:
                    break

            # Fall back to random placement
            if not placed_ok:
                for _attempt in range(count * 3 + 50):
                    rx = int(rng.integers(5, max(6, w - room_w - 5)))
                    ry = int(rng.integers(5, max(6, h - room_h - 5)))
                    if self._check_no_overlap(rx, ry, room_w, room_h, placed, w, h):
                        placed_ok = True
                        break

            if placed_ok:
                node.position = (rx, ry)
                node.size = (room_w, room_h)
                placed.append((rx, ry, room_w, room_h))
                self._draw_filled_rect(state, rx, ry, room_w, room_h, floor_color, wall_color)
                state.entities.append(Entity(
                    entity_type="room",
                    position=(rx, ry),
                    size=(room_w, room_h),
                    variant="graph_room",
                    metadata={"name": node.node_id, "zone": node.zone}
                ))
            else:
                # Emergency: place at margin, clamped to map bounds
                rx = 5
                ry = min(h - room_h - 5, 5 + len(placed) * (max_room + 5))
                ry = max(5, ry)
                room_w = min(room_w, w - rx - 5)
                room_h = min(room_h, h - ry - 5)
                if room_w < 5 or room_h < 5:
                    # Map too small for more rooms — skip this one
                    node.position = (5, 5)
                    node.size = (5, 5)
                    continue
                node.position = (rx, ry)
                node.size = (room_w, room_h)
                placed.append((rx, ry, room_w, room_h))
                self._draw_filled_rect(state, rx, ry, room_w, room_h, floor_color, wall_color)

        return {"rooms_placed": len(placed), "mode": "room_graph", "status": "completed"}

    def _check_no_overlap(self, rx, ry, rw, rh, placed, map_w, map_h, buffer=4):
        """Return True if rect (rx,ry,rw,rh) fits inside map bounds and doesn't overlap placed rooms."""
        if rx < 2 or ry < 2 or rx + rw >= map_w - 2 or ry + rh >= map_h - 2:
            return False
        for ex, ey, ew, eh in placed:
            if (rx < ex + ew + buffer and rx + rw + buffer > ex and
                    ry < ey + eh + buffer and ry + rh + buffer > ey):
                return False
        return True

    # ── Helper methods ──────────────────────────────────────────────────

    def _place_random_rooms(self, state, rng, count, floor_color, wall_color,
                             entity_variant="room", min_room_frac=10, max_room_frac=5):
        """Place non-overlapping rectangular rooms. Returns list of (x,y,w,h)."""
        h, w = state.config.height, state.config.width
        min_room = max(15, w // min_room_frac)
        max_room = max(30, w // max_room_frac)

        rooms = []
        for _ in range(count * 3):
            rw = rng.integers(min_room, max_room)
            rh = rng.integers(min_room, max_room)
            rx = rng.integers(5, w - rw - 5)
            ry = rng.integers(5, h - rh - 5)

            overlap = False
            for (ex, ey, ew, eh) in rooms:
                if (rx < ex + ew + 4 and rx + rw + 4 > ex and
                    ry < ey + eh + 4 and ry + rh + 4 > ey):
                    overlap = True
                    break

            if not overlap:
                rooms.append((rx, ry, rw, rh))
                self._draw_filled_rect(state, rx, ry, rw, rh, floor_color, wall_color)
                state.entities.append(Entity(
                    entity_type="room",
                    position=(rx, ry),
                    size=(rw, rh),
                    variant=entity_variant,
                    metadata={"name": f"Chamber {len(state.entities) + 1}"}
                ))
                if len(rooms) >= count:
                    break

        return rooms

    def _connect_rooms_corridors(self, state, rooms, rng, floor_color, corridor_w=3):
        """Connect rooms with L-shaped corridors. Returns corridor count."""
        h, w = state.config.height, state.config.width
        corridors = 0

        for i in range(len(rooms) - 1):
            r1, r2 = rooms[i], rooms[i + 1]
            cx1 = r1[0] + r1[2] // 2
            cy1 = r1[1] + r1[3] // 2
            cx2 = r2[0] + r2[2] // 2
            cy2 = r2[1] + r2[3] // 2

            hw = corridor_w // 2
            if rng.random() < 0.5:
                for x in range(min(cx1, cx2), max(cx1, cx2) + 1):
                    for dy in range(-hw, hw + 1):
                        ny = cy1 + dy
                        if 0 <= x < w and 0 <= ny < h:
                            state.walkability[ny, x] = True
                            state.terrain_color[ny, x] = floor_color
                for y in range(min(cy1, cy2), max(cy1, cy2) + 1):
                    for dx in range(-hw, hw + 1):
                        nx = cx2 + dx
                        if 0 <= nx < w and 0 <= y < h:
                            state.walkability[y, nx] = True
                            state.terrain_color[y, nx] = floor_color
            else:
                for y in range(min(cy1, cy2), max(cy1, cy2) + 1):
                    for dx in range(-hw, hw + 1):
                        nx = cx1 + dx
                        if 0 <= nx < w and 0 <= y < h:
                            state.walkability[y, nx] = True
                            state.terrain_color[y, nx] = floor_color
                for x in range(min(cx1, cx2), max(cx1, cx2) + 1):
                    for dy in range(-hw, hw + 1):
                        ny = cy2 + dy
                        if 0 <= x < w and 0 <= ny < h:
                            state.walkability[ny, x] = True
                            state.terrain_color[ny, x] = floor_color
            corridors += 1

        return corridors

    def _draw_rect_walls(self, state, x1, y1, x2, y2, thick, wall_color, floor_color):
        """Draw a rectangular perimeter wall with interior floor."""
        h, w = state.config.height, state.config.width
        for y in range(max(0, y1), min(h, y2)):
            for x in range(max(0, x1), min(w, x2)):
                is_wall = (y < y1 + thick or y >= y2 - thick or
                           x < x1 + thick or x >= x2 - thick)
                if is_wall:
                    state.walkability[y, x] = False
                    state.structure_mask[y, x] = True
                    state.terrain_color[y, x] = wall_color
                else:
                    state.walkability[y, x] = True
                    state.terrain_color[y, x] = floor_color

    def _draw_filled_rect(self, state, rx, ry, rw, rh, fill_color, wall_color):
        """Draw a filled rectangle with walls on the border."""
        h, w = state.config.height, state.config.width
        for by in range(max(0, ry), min(h, ry + rh)):
            for bx in range(max(0, rx), min(w, rx + rw)):
                is_border = (by == ry or by == ry + rh - 1 or
                             bx == rx or bx == rx + rw - 1)
                if is_border:
                    state.terrain_color[by, bx] = wall_color
                    state.walkability[by, bx] = False
                else:
                    state.terrain_color[by, bx] = fill_color
                    state.walkability[by, bx] = True
                state.structure_mask[by, bx] = True

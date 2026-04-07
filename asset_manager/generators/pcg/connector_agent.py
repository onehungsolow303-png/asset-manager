"""
ConnectorAgent — Carves corridors between connected rooms, places doors,
and creates stair transitions.

Reads a RoomGraph from SharedState (rooms must have position and size set),
then for each edge carves an L-shaped corridor between the two room centres,
optionally places a door Entity at the corridor-room boundary, and converts
"stairs" edges into Transition records.
"""

import numpy as np
from base_agent import BaseAgent
from shared_state import SharedState, Entity, PathSegment, Transition
from typing import Any

# Floor tile colour used when carving corridors
_FLOOR_COLOR = (75, 70, 62)

# Corridor width (in tiles) per corridor style
_STYLE_WIDTH: dict[str, int] = {
    "carved": 2,
    "built": 3,
    "natural": 2,
    "hallway": 2,
    "road": 4,
}


class ConnectorAgent(BaseAgent):
    name = "ConnectorAgent"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        graph = shared_state.room_graph
        if graph is None:
            return {"skipped": True, "corridors": 0}

        corridor_style: str = params.get("corridor_style", "carved")
        door_frequency: float = float(params.get("door_frequency", 0.5))
        corridor_width: int = _STYLE_WIDTH.get(corridor_style, 2)

        rng = np.random.default_rng(shared_state.config.seed + 900)

        map_h = shared_state.config.height
        map_w = shared_state.config.width

        corridors_carved = 0
        doors_placed = 0
        stairs_created = 0

        for edge in graph.edges:
            node_a = graph.get_node(edge.from_id)
            node_b = graph.get_node(edge.to_id)

            if node_a.position is None or node_a.size is None:
                continue
            if node_b.position is None or node_b.size is None:
                continue

            # Room centres (position is top-left corner)
            cx1 = node_a.position[0] + node_a.size[0] // 2
            cy1 = node_a.position[1] + node_a.size[1] // 2
            cx2 = node_b.position[0] + node_b.size[0] // 2
            cy2 = node_b.position[1] + node_b.size[1] // 2

            # Decide orientation: 50 % horizontal-first, 50 % vertical-first
            horizontal_first: bool = bool(rng.integers(0, 2))

            half_w = corridor_width // 2
            waypoints: list[tuple[int, int]] = [(cx1, cy1)]

            if horizontal_first:
                # Horizontal segment at cy1, then vertical segment at cx2
                x_min = np.clip(min(cx1, cx2), 0, map_w - 1)
                x_max = np.clip(max(cx1, cx2), 0, map_w - 1)
                y_min_seg = np.clip(cy1 - half_w, 0, map_h - 1)
                y_max_seg = np.clip(cy1 + corridor_width - half_w, 0, map_h - 1)
                shared_state.walkability[y_min_seg:y_max_seg + 1, x_min:x_max + 1] = True
                shared_state.terrain_color[y_min_seg:y_max_seg + 1, x_min:x_max + 1] = _FLOOR_COLOR

                bend_x = int(np.clip(cx2, 0, map_w - 1))
                waypoints.append((bend_x, cy1))

                y_min2 = np.clip(min(cy1, cy2), 0, map_h - 1)
                y_max2 = np.clip(max(cy1, cy2), 0, map_h - 1)
                x_min_seg2 = np.clip(cx2 - half_w, 0, map_w - 1)
                x_max_seg2 = np.clip(cx2 + corridor_width - half_w, 0, map_w - 1)
                shared_state.walkability[y_min2:y_max2 + 1, x_min_seg2:x_max_seg2 + 1] = True
                shared_state.terrain_color[y_min2:y_max2 + 1, x_min_seg2:x_max_seg2 + 1] = _FLOOR_COLOR

            else:
                # Vertical segment at cx1, then horizontal segment at cy2
                y_min = np.clip(min(cy1, cy2), 0, map_h - 1)
                y_max = np.clip(max(cy1, cy2), 0, map_h - 1)
                x_min_seg = np.clip(cx1 - half_w, 0, map_w - 1)
                x_max_seg = np.clip(cx1 + corridor_width - half_w, 0, map_w - 1)
                shared_state.walkability[y_min:y_max + 1, x_min_seg:x_max_seg + 1] = True
                shared_state.terrain_color[y_min:y_max + 1, x_min_seg:x_max_seg + 1] = _FLOOR_COLOR

                bend_y = int(np.clip(cy2, 0, map_h - 1))
                waypoints.append((cx1, bend_y))

                x_min2 = np.clip(min(cx1, cx2), 0, map_w - 1)
                x_max2 = np.clip(max(cx1, cx2), 0, map_w - 1)
                y_min_seg2 = np.clip(cy2 - half_w, 0, map_h - 1)
                y_max_seg2 = np.clip(cy2 + corridor_width - half_w, 0, map_h - 1)
                shared_state.walkability[y_min_seg2:y_max_seg2 + 1, x_min2:x_max2 + 1] = True
                shared_state.terrain_color[y_min_seg2:y_max_seg2 + 1, x_min2:x_max2 + 1] = _FLOOR_COLOR

            waypoints.append((cx2, cy2))

            # Record path segment
            shared_state.paths.append(PathSegment(
                path_type="corridor",
                waypoints=waypoints,
                width=corridor_width,
                metadata={"from": edge.from_id, "to": edge.to_id, "style": corridor_style},
            ))
            corridors_carved += 1

            # Door placement
            place_door = (
                edge.connection_type == "door"
                or (edge.connection_type == "corridor" and rng.random() < door_frequency)
            )
            if place_door:
                # Place door at the midpoint of the first corridor waypoint transition
                door_x = int(np.clip((cx1 + cx2) // 2, 0, map_w - 1))
                door_y = int(np.clip((cy1 + cy2) // 2, 0, map_h - 1))
                shared_state.entities.append(Entity(
                    entity_type="door",
                    position=(door_x, door_y),
                    size=(1, 1),
                    variant="wood",
                    metadata={"from": edge.from_id, "to": edge.to_id},
                ))
                doors_placed += 1

            # Stair transitions
            if edge.connection_type == "stairs":
                mid_x = int(np.clip((cx1 + cx2) // 2, 0, map_w - 1))
                mid_y = int(np.clip((cy1 + cy2) // 2, 0, map_h - 1))
                shared_state.transitions.append(Transition(
                    x=mid_x,
                    y=mid_y,
                    from_z=0,
                    to_z=-1,
                    transition_type="stairs_down",
                ))
                stairs_created += 1

        return {
            "skipped": False,
            "corridors": corridors_carved,
            "doors": doors_placed,
            "stairs": stairs_created,
            "corridor_style": corridor_style,
            "corridor_width": corridor_width,
        }

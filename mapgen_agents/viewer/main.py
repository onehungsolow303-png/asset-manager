"""Pygame playtest viewer entry point.

Usage: python main.py <map_directory>
"""

import os
import sys

# Add viewer directory and parent to sys.path for imports
_viewer_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_viewer_dir)
for p in (_viewer_dir, _parent_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

import pygame
from config import (
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT, FPS, TILE_SIZE,
    KEY_MOVE_UP, KEY_MOVE_DOWN, KEY_MOVE_LEFT, KEY_MOVE_RIGHT,
    KEY_INTERACT, KEY_END_TURN, KEY_TOGGLE_PERSPECTIVE,
    KEY_ZLEVEL_UP, KEY_ZLEVEL_DOWN, KEY_TOGGLE_GRID, KEY_TOGGLE_FOG,
    KEY_QUIT,
)
from map_loader import load_map
from entities import Creature
from camera import Camera
from fog_of_war import FogOfWar
from game_engine import GameEngine, GameState
from renderer import Renderer
from ui_overlay import UIOverlay


def _find_map_dir(path: str) -> str:
    """Resolve a map directory: if path contains map_data.json, use it.
    Otherwise look for subdirectories with map_data.json."""
    if os.path.isfile(os.path.join(path, "map_data.json")):
        return path
    # Maybe the user passed the output root -- find first subdir with map_data
    for entry in sorted(os.listdir(path)):
        sub = os.path.join(path, entry)
        if os.path.isdir(sub) and os.path.isfile(os.path.join(sub, "map_data.json")):
            return sub
    return path  # fall back, will error on load


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <map_directory>")
        sys.exit(1)

    map_path = sys.argv[1]
    map_dir = _find_map_dir(map_path)
    print(f"Loading map from: {map_dir}")

    # ------------------------------------------------------------------
    # Init pygame
    # ------------------------------------------------------------------
    pygame.init()
    screen = pygame.display.set_mode(
        (WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE
    )
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    # ------------------------------------------------------------------
    # Load map and create game objects
    # ------------------------------------------------------------------
    game_map = load_map(map_dir)
    print(f"Map: {game_map.width}x{game_map.height}, "
          f"z-levels: {game_map.z_levels}, "
          f"spawns: {len(game_map.spawns)}, "
          f"transitions: {len(game_map.transitions)}")

    # Create creatures from spawns
    player = None
    creatures: list[Creature] = []

    for sp in game_map.spawns:
        c = Creature.from_spawn(sp)
        creatures.append(c)
        if c.token_type == "player":
            player = c

    # If no player spawn, create a default player at map centre
    if player is None:
        z0 = game_map.z_levels[0] if game_map.z_levels else 0
        player = Creature(
            name="Player", x=game_map.width // 2, y=game_map.height // 2,
            z=z0, token_type="player", hp=20, max_hp=20, ac=14,
            strength=14, dexterity=12, speed=6, atk_dice="1d8+2",
        )
        creatures.insert(0, player)
        print("No player spawn found -- created default player at map centre")

    # ------------------------------------------------------------------
    # Create systems
    # ------------------------------------------------------------------
    camera = Camera(WINDOW_WIDTH, WINDOW_HEIGHT)
    camera._player_z = player.z

    renderer = Renderer(screen, game_map)
    fog = FogOfWar()

    # Initial fog update
    fog.update(player.x, player.y, player.z, game_map.walkability)

    engine = GameEngine(player, creatures, game_map, fog)
    ui = UIOverlay(screen)

    # Centre camera on player
    camera.follow(player.x * TILE_SIZE + TILE_SIZE / 2,
                  player.y * TILE_SIZE + TILE_SIZE / 2)
    # Snap camera instantly
    camera.x = camera._target_x
    camera.y = camera._target_y

    # ------------------------------------------------------------------
    # Middle-mouse panning state
    # ------------------------------------------------------------------
    panning = False
    pan_start = (0, 0)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    running = True
    while running:
        dt = clock.tick(FPS)

        for event in pygame.event.get():
            # ---- Quit ----
            if event.type == pygame.QUIT:
                running = False
                continue

            # ---- Key down ----
            if event.type == pygame.KEYDOWN:
                if event.key == KEY_QUIT:
                    running = False
                    continue

                # Movement (exploration only)
                if engine.state == GameState.EXPLORATION:
                    dx, dy = 0, 0
                    if event.key in KEY_MOVE_UP:
                        dy = -1
                    elif event.key in KEY_MOVE_DOWN:
                        dy = 1
                    elif event.key in KEY_MOVE_LEFT:
                        dx = -1
                    elif event.key in KEY_MOVE_RIGHT:
                        dx = 1

                    if dx != 0 or dy != 0:
                        _try_move(player, dx, dy, game_map, creatures, fog,
                                  camera)

                # Combat movement (player's turn)
                elif engine.state == GameState.COMBAT:
                    current = engine.combat.current_creature
                    if current is not None and current.token_type == "player":
                        dx, dy = 0, 0
                        if event.key in KEY_MOVE_UP:
                            dy = -1
                        elif event.key in KEY_MOVE_DOWN:
                            dy = 1
                        elif event.key in KEY_MOVE_LEFT:
                            dx = -1
                        elif event.key in KEY_MOVE_RIGHT:
                            dx = 1

                        if (dx != 0 or dy != 0) and current.movement_remaining > 0:
                            _try_move(current, dx, dy, game_map, creatures,
                                      fog, camera)

                # Interact (transitions)
                if event.key == KEY_INTERACT:
                    _interact(player, game_map, engine, fog, camera)

                # End turn (combat)
                if event.key == KEY_END_TURN:
                    engine.player_end_turn()

                # Toggle perspective
                if event.key == KEY_TOGGLE_PERSPECTIVE:
                    camera.toggle_perspective()

                # Toggle grid
                if event.key == KEY_TOGGLE_GRID:
                    renderer.toggle_grid()

                # Toggle fog
                if event.key == KEY_TOGGLE_FOG:
                    fog.toggle()

                # Force z-level change
                if event.key == KEY_ZLEVEL_UP:
                    _force_z_change(player, 1, game_map, fog, camera)
                if event.key == KEY_ZLEVEL_DOWN:
                    _force_z_change(player, -1, game_map, fog, camera)

            # ---- Mouse wheel (zoom) ----
            if event.type == pygame.MOUSEWHEEL:
                if event.y > 0:
                    camera.zoom_in()
                elif event.y < 0:
                    camera.zoom_out()

            # ---- Middle mouse (pan) ----
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
                panning = True
                pan_start = event.pos

            if event.type == pygame.MOUSEBUTTONUP and event.button == 2:
                panning = False

            if event.type == pygame.MOUSEMOTION and panning:
                dx = event.pos[0] - pan_start[0]
                dy = event.pos[1] - pan_start[1]
                camera.pan(-dx, -dy)
                pan_start = event.pos

            # ---- Left click (combat: attack enemy at tile) ----
            if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                    and engine.state == GameState.COMBAT):
                wx, wy = camera.screen_to_world(event.pos[0], event.pos[1])
                tile_x = int(wx / TILE_SIZE)
                tile_y = int(wy / TILE_SIZE)
                _click_attack(engine, tile_x, tile_y, creatures, player)

            # ---- Window resize ----
            if event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(
                    (event.w, event.h), pygame.RESIZABLE
                )
                camera.resize(event.w, event.h)
                renderer.screen = screen
                ui.screen = screen

        # ---- Mouse position for parallax ----
        if camera.perspective_mode:
            mx, my = pygame.mouse.get_pos()
            camera.set_mouse(mx, my)

        # ---- Update systems ----
        engine.update()
        fog.update(player.x, player.y, player.z, game_map.walkability)
        camera.follow(player.x * TILE_SIZE + TILE_SIZE / 2,
                      player.y * TILE_SIZE + TILE_SIZE / 2)
        camera.update()

        # ---- Render ----
        renderer.render(camera, creatures, fog, player.z, engine)
        ui.render(engine, player, creatures, camera, fog=fog, game_map=game_map)
        pygame.display.flip()

    pygame.quit()


# ======================================================================
# Helper functions
# ======================================================================

def _try_move(creature: Creature, dx: int, dy: int, game_map, creatures,
              fog, camera):
    """Try to move a creature by (dx, dy). Checks walkability and collisions."""
    nx = creature.x + dx
    ny = creature.y + dy

    walk = game_map.walkability.get(creature.z)
    if walk is None:
        return

    h, w = walk.shape
    if not (0 <= nx < w and 0 <= ny < h):
        return

    if not walk[ny, nx]:
        return

    # Check collision with other alive creatures
    for c in creatures:
        if c is not creature and c.alive and c.x == nx and c.y == ny and c.z == creature.z:
            return

    creature.x = nx
    creature.y = ny

    # Update camera z tracking
    camera._player_z = creature.z


def _interact(player, game_map, engine, fog, camera):
    """Check transitions at player position and change z-level."""
    for t in game_map.transitions:
        if t["x"] == player.x and t["y"] == player.y and t["from_z"] == player.z:
            target_z = t["to_z"]
            if target_z in game_map.walkability:
                player.z = target_z
                camera._player_z = target_z
                fog.update(player.x, player.y, player.z, game_map.walkability)
                engine.log.append(
                    f"Moved to z-level {target_z} via {t.get('type', 'transition')}"
                )
                return
    engine.log.append("Nothing to interact with here.")


def _force_z_change(player, direction, game_map, fog, camera):
    """Force z-level change by +/-1."""
    z_levels = game_map.z_levels
    if not z_levels:
        return
    idx = z_levels.index(player.z) if player.z in z_levels else 0
    new_idx = max(0, min(len(z_levels) - 1, idx + direction))
    player.z = z_levels[new_idx]
    camera._player_z = player.z
    fog.update(player.x, player.y, player.z, game_map.walkability)


def _click_attack(engine, tile_x, tile_y, creatures, player):
    """Attack enemy at clicked tile during combat."""
    for c in creatures:
        if (c.token_type == "enemy" and c.alive
                and c.x == tile_x and c.y == tile_y
                and c.z == player.z):
            engine.player_attack_target(c)
            return


if __name__ == "__main__":
    main()

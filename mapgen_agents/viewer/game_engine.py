"""Game state machine: exploration vs combat."""

import math
from enum import Enum

from entities import Creature
from combat import CombatManager
from ai import ai_turn, manhattan_dist
from fog_of_war import FogOfWar, VISIBLE
from config import COMBAT_DETECT_RANGE


class GameState(Enum):
    EXPLORATION = "exploration"
    COMBAT = "combat"
    GAME_OVER = "game_over"


class GameEngine:
    """Top-level state machine managing exploration and combat."""

    def __init__(self, player: Creature, creatures: list[Creature],
                 game_map, fog: FogOfWar):
        self.player = player
        self.creatures = creatures
        self.game_map = game_map
        self.fog = fog
        self.state = GameState.EXPLORATION
        self.combat = CombatManager()
        self.log: list[str] = ["Welcome to the dungeon. WASD to move, F to interact."]
        self._ai_turn_timer = 0  # frames to wait before processing AI turns
        self._ai_turn_delay = 20  # frames between AI turns in combat

    def update(self):
        """Main update tick. Call once per frame."""
        if self.state == GameState.EXPLORATION:
            self._check_combat_trigger()
        elif self.state == GameState.COMBAT:
            self._process_combat()

    def _check_combat_trigger(self):
        """Check if an enemy is close enough (and visible) to trigger combat."""
        pz = self.player.z
        for c in self.creatures:
            if (c.token_type == "enemy" and c.alive and c.z == pz
                    and manhattan_dist(c.x, c.y, self.player.x, self.player.y)
                    <= COMBAT_DETECT_RANGE):
                # Check LOS: enemy must be visible through fog
                if self.fog.is_visible(c.x, c.y, pz):
                    self._enter_combat()
                    return

    def _enter_combat(self):
        """Gather nearby enemies + player and start combat."""
        pz = self.player.z
        combatants = [self.player]

        for c in self.creatures:
            if (c.token_type == "enemy" and c.alive and c.z == pz
                    and manhattan_dist(c.x, c.y, self.player.x, self.player.y)
                    <= COMBAT_DETECT_RANGE):
                combatants.append(c)

        self.state = GameState.COMBAT
        self.combat.start_combat(combatants)
        self.log.append("Combat started!")
        self.log.extend(self.combat.log[-len(combatants) - 2:])
        self._ai_turn_timer = 0

    def _process_combat(self):
        """Process enemy turns automatically during combat."""
        if not self.combat.active:
            return

        current = self.combat.current_creature
        if current is None:
            return

        # If it's the player's turn, wait for input
        if current.token_type == "player":
            return

        # AI turn with a delay for visual feedback
        self._ai_turn_timer += 1
        if self._ai_turn_timer < self._ai_turn_delay:
            return
        self._ai_turn_timer = 0

        # Execute AI turn
        walkability = self.game_map.walkability.get(self.player.z)
        if walkability is not None:
            messages = ai_turn(current, self.player, walkability, self.creatures)
            self.log.extend(messages)
            self.combat.log.extend(messages)

        # Check if combat ends
        result = self.combat.check_combat_end()
        if result == "victory":
            self.log.append("Victory! All enemies defeated.")
            self.combat.end_combat()
            self.state = GameState.EXPLORATION
        elif result == "game_over":
            self.log.append("Game Over! You have been defeated.")
            self.state = GameState.GAME_OVER
        else:
            self.combat.next_turn()

    def player_end_turn(self):
        """Player ends their combat turn."""
        if self.state != GameState.COMBAT:
            return
        if not self.combat.active:
            return

        current = self.combat.current_creature
        if current is not None and current.token_type == "player":
            self.combat.next_turn()

    def player_attack_target(self, target: Creature):
        """Resolve player attack in combat."""
        if self.state != GameState.COMBAT:
            return
        if not self.combat.active:
            return

        current = self.combat.current_creature
        if current is None or current.token_type != "player":
            self.log.append("Not your turn!")
            return

        if not current.has_action:
            self.log.append("No action remaining this turn!")
            return

        # Check adjacency
        if manhattan_dist(current.x, current.y, target.x, target.y) > 1:
            self.log.append("Target is too far away! (must be adjacent)")
            return

        messages = self.combat.player_attack(current, target)
        self.log.extend(messages)

        # Check combat end
        result = self.combat.check_combat_end()
        if result == "victory":
            self.log.append("Victory! All enemies defeated.")
            self.combat.end_combat()
            self.state = GameState.EXPLORATION
        elif result == "game_over":
            self.log.append("Game Over! You have been defeated.")
            self.state = GameState.GAME_OVER

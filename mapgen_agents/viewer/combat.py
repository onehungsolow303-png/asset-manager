"""D20 combat manager: initiative, turns, attacks."""

from entities import Creature, ability_modifier


class CombatManager:
    """Manages turn-based D20 combat."""

    def __init__(self):
        self.active = False
        self.turn_order: list[Creature] = []
        self.current_index = 0
        self.round_number = 0
        self.log: list[str] = []

    @property
    def current_creature(self) -> Creature | None:
        """Who's up in the turn order."""
        if not self.active or not self.turn_order:
            return None
        return self.turn_order[self.current_index]

    def start_combat(self, combatants: list[Creature]):
        """Roll initiative and start combat."""
        self.active = True
        self.round_number = 1
        self.current_index = 0
        self.log = []

        # Roll initiative: d20 + DEX modifier, sort descending
        initiatives = []
        for c in combatants:
            init_roll = c.roll_initiative()
            initiatives.append((init_roll, c))
            self.log.append(f"{c.name} rolls initiative: {init_roll}")

        initiatives.sort(key=lambda x: x[0], reverse=True)
        self.turn_order = [c for _, c in initiatives]

        self.log.append(f"--- Round {self.round_number} ---")

        # Start first creature's turn
        if self.turn_order:
            self.turn_order[0].start_turn()
            self.log.append(f"{self.turn_order[0].name}'s turn")

    def next_turn(self):
        """Advance to next alive creature, increment round on wrap."""
        if not self.active or not self.turn_order:
            return

        # Find next alive creature
        start = self.current_index
        while True:
            self.current_index = (self.current_index + 1) % len(self.turn_order)

            # Wrapped around = new round
            if self.current_index == 0:
                self.round_number += 1
                self.log.append(f"--- Round {self.round_number} ---")

            creature = self.turn_order[self.current_index]
            if creature.alive:
                creature.start_turn()
                self.log.append(f"{creature.name}'s turn")
                break

            # Safety: if we loop back to start, all dead
            if self.current_index == start:
                break

    def end_combat(self):
        """End combat mode."""
        self.active = False
        self.turn_order = []
        self.current_index = 0

    def player_attack(self, attacker: Creature, target: Creature) -> list[str]:
        """Player attacks a target. Returns log strings."""
        log: list[str] = []

        if not attacker.has_action:
            log.append("No action remaining!")
            return log

        attacker.has_action = False
        attack_roll = attacker.roll_attack()

        if attack_roll >= target.ac:
            dmg = attacker.roll_damage()
            target.take_damage(dmg)
            log.append(f"{attacker.name} hits {target.name} for {dmg} damage! "
                       f"(roll {attack_roll} vs AC {target.ac})")
            if not target.alive:
                log.append(f"{target.name} has been defeated!")
        else:
            log.append(f"{attacker.name} misses {target.name}. "
                       f"(roll {attack_roll} vs AC {target.ac})")

        self.log.extend(log)
        return log

    def check_combat_end(self) -> str | None:
        """Check if combat should end.

        Returns: 'victory' if all enemies dead, 'game_over' if player dead,
                 None if combat continues.
        """
        if not self.active:
            return None

        player = None
        enemies_alive = False

        for c in self.turn_order:
            if c.token_type == "player":
                player = c
            elif c.token_type == "enemy" and c.alive:
                enemies_alive = True

        if player and not player.alive:
            return "game_over"
        if not enemies_alive:
            return "victory"
        return None

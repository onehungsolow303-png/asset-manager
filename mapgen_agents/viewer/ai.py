"""Enemy AI: chase, patrol, guard behaviors."""

from entities import Creature, ability_modifier
from config import MOVEMENT_PER_TURN


def manhattan_dist(x1: int, y1: int, x2: int, y2: int) -> int:
    """Manhattan distance between two points."""
    return abs(x1 - x2) + abs(y1 - y2)


def move_toward(creature: Creature, target_x: int, target_y: int,
                walkability, creatures: list[Creature],
                max_steps: int = 1) -> bool:
    """Move creature toward target one tile at a time.

    Checks walkability and avoids other alive creatures.
    Returns True if any movement happened.
    """
    moved = False
    h, w = walkability.shape

    # Build set of occupied tiles (alive creatures only, excluding self)
    occupied = set()
    for c in creatures:
        if c is not creature and c.alive:
            occupied.add((c.x, c.y))

    for _ in range(max_steps):
        if creature.movement_remaining <= 0:
            break

        dx = target_x - creature.x
        dy = target_y - creature.y
        if dx == 0 and dy == 0:
            break

        # Pick best step direction (prefer larger delta axis)
        candidates = []
        if abs(dx) >= abs(dy):
            candidates.append((1 if dx > 0 else -1, 0))
            if dy != 0:
                candidates.append((0, 1 if dy > 0 else -1))
        else:
            candidates.append((0, 1 if dy > 0 else -1))
            if dx != 0:
                candidates.append((1 if dx > 0 else -1, 0))

        stepped = False
        for sx, sy in candidates:
            nx, ny = creature.x + sx, creature.y + sy
            if 0 <= nx < w and 0 <= ny < h:
                if walkability[ny, nx] and (nx, ny) not in occupied:
                    creature.x = nx
                    creature.y = ny
                    creature.movement_remaining -= 1
                    occupied.discard((creature.x - sx, creature.y - sy))
                    occupied.add((nx, ny))
                    stepped = True
                    moved = True
                    break

        if not stepped:
            break

    return moved


def ai_turn(creature: Creature, player: Creature, walkability,
            all_creatures: list[Creature]) -> list[str]:
    """Execute one AI turn for a creature.

    Returns a list of combat log strings.
    """
    log: list[str] = []

    if not creature.alive:
        return log

    creature.start_turn()

    # If adjacent, attack immediately
    if manhattan_dist(creature.x, creature.y, player.x, player.y) <= 1:
        if creature.has_action:
            log.extend(_attack(creature, player))
        return log

    # Move toward player
    move_toward(creature, player.x, player.y, walkability,
                all_creatures, max_steps=creature.movement_remaining)

    # If now adjacent, attack
    if manhattan_dist(creature.x, creature.y, player.x, player.y) <= 1:
        if creature.has_action:
            log.extend(_attack(creature, player))

    return log


def _attack(attacker: Creature, target: Creature) -> list[str]:
    """Resolve an attack. Returns log strings."""
    log: list[str] = []
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
    return log

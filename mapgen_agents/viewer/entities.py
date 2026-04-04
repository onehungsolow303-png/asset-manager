"""Game entities: Player, Enemy, NPC with d20 stat blocks."""
import random
from dataclasses import dataclass, field


def roll_dice(dice_str: str) -> int:
    """Parse and roll dice notation like '1d8+3', '2d6', '1d4'."""
    dice_str = dice_str.strip()
    bonus = 0
    if "+" in dice_str:
        parts = dice_str.split("+")
        dice_str = parts[0]
        bonus = int(parts[1])
    elif "-" in dice_str:
        parts = dice_str.split("-")
        dice_str = parts[0]
        bonus = -int(parts[1])
    num, sides = dice_str.split("d")
    num = int(num)
    sides = int(sides)
    total = sum(random.randint(1, sides) for _ in range(num))
    return total + bonus


def ability_modifier(score: int) -> int:
    """D20 ability modifier: (score - 10) // 2"""
    return (score - 10) // 2


@dataclass
class Creature:
    """Base creature with d20 stats."""
    name: str
    x: int
    y: int
    z: int
    token_type: str
    ai_behavior: str = "static"
    hp: int = 10
    max_hp: int = 10
    ac: int = 10
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    speed: int = 6
    atk_dice: str = "1d4"
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10
    alive: bool = True
    movement_remaining: int = 0
    has_action: bool = True
    visible: bool = False

    @classmethod
    def from_spawn(cls, spawn_data: dict) -> "Creature":
        raw_stats = spawn_data.get("stats", {})
        # Normalise keys to uppercase for consistent lookup
        stats = {k.upper(): v for k, v in raw_stats.items()}
        hp = stats.get("HP", 10)
        return cls(
            name=spawn_data["name"], x=spawn_data["x"], y=spawn_data["y"],
            z=spawn_data["z"], token_type=spawn_data["token_type"],
            ai_behavior=spawn_data.get("ai_behavior", "static"),
            hp=hp, max_hp=hp, ac=stats.get("AC", 10),
            strength=stats.get("STR", 10), dexterity=stats.get("DEX", 10),
            constitution=stats.get("CON", 10), speed=stats.get("SPD", 6),
            atk_dice=stats.get("ATK", "1d4"),
            intelligence=stats.get("INT", 10), wisdom=stats.get("WIS", 10),
            charisma=stats.get("CHA", 10),
        )

    def roll_initiative(self) -> int:
        return roll_dice("1d20") + ability_modifier(self.dexterity)

    def roll_attack(self) -> int:
        return roll_dice("1d20") + ability_modifier(self.strength)

    def roll_damage(self) -> int:
        return max(1, roll_dice(self.atk_dice))

    def take_damage(self, amount: int):
        self.hp = max(0, self.hp - amount)
        if self.hp == 0:
            self.alive = False

    def start_turn(self):
        self.movement_remaining = self.speed
        self.has_action = True

    @property
    def hp_pct(self) -> float:
        return self.hp / self.max_hp if self.max_hp > 0 else 0

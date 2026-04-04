"""Tests for d20 combat math."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mapgen_agents', 'viewer'))

from entities import roll_dice, ability_modifier, Creature


def test_ability_modifier():
    assert ability_modifier(10) == 0
    assert ability_modifier(16) == 3
    assert ability_modifier(8) == -1
    assert ability_modifier(20) == 5
    assert ability_modifier(1) == -5


def test_roll_dice_simple():
    for _ in range(100):
        result = roll_dice("1d6")
        assert 1 <= result <= 6


def test_roll_dice_with_bonus():
    for _ in range(100):
        result = roll_dice("1d6+3")
        assert 4 <= result <= 9


def test_roll_dice_multi():
    for _ in range(100):
        result = roll_dice("2d6")
        assert 2 <= result <= 12


def test_creature_from_spawn():
    spawn = {
        "x": 10, "y": 20, "z": 0,
        "token_type": "enemy", "name": "Goblin",
        "stats": {"HP": 7, "AC": 15, "STR": 8, "DEX": 14, "CON": 10, "SPD": 6, "ATK": "1d6+2"},
        "ai_behavior": "chase",
    }
    c = Creature.from_spawn(spawn)
    assert c.hp == 7
    assert c.max_hp == 7
    assert c.ac == 15
    assert c.atk_dice == "1d6+2"
    assert c.alive


def test_creature_take_damage():
    c = Creature(name="Test", x=0, y=0, z=0, token_type="enemy", hp=10, max_hp=10)
    c.take_damage(3)
    assert c.hp == 7
    assert c.alive
    c.take_damage(7)
    assert c.hp == 0
    assert not c.alive


def test_creature_start_turn():
    c = Creature(name="Test", x=0, y=0, z=0, token_type="player", speed=6)
    c.start_turn()
    assert c.movement_remaining == 6
    assert c.has_action

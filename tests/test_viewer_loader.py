"""Tests for the viewer map loader."""
import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mapgen_agents', 'viewer'))

import numpy as np
from PIL import Image
from map_loader import load_map


def _make_test_map(tmp_dir):
    w, h = 32, 32
    img = Image.fromarray(np.full((h, w, 3), 100, dtype=np.uint8), "RGB")
    img.save(os.path.join(tmp_dir, "z_0.png"))

    data = {
        "config": {"width": w, "height": h, "biome": "forest", "map_type": "village", "seed": 42},
        "z_levels": [
            {"z": 0, "terrain_png": "z_0.png", "walkability": [1] * (w * h), "entities": []},
        ],
        "transitions": [{"x": 16, "y": 16, "from_z": 0, "to_z": -1, "type": "stairs_down"}],
        "spawns": [
            {"x": 5, "y": 5, "z": 0, "token_type": "player", "name": "Hero",
             "stats": {"HP": 30, "AC": 15}, "ai_behavior": "static"},
        ],
        "labels": [],
    }
    json_path = os.path.join(tmp_dir, "map_data.json")
    with open(json_path, "w") as f:
        json.dump(data, f)
    return json_path


def test_load_map_basic():
    with tempfile.TemporaryDirectory() as tmp:
        _make_test_map(tmp)
        game_map = load_map(tmp)
        assert game_map.width == 32
        assert game_map.height == 32
        assert game_map.config["biome"] == "forest"
        assert 0 in game_map.terrain_surfaces
        assert len(game_map.transitions) == 1
        assert len(game_map.spawns) == 1
        assert game_map.spawns[0]["token_type"] == "player"


def test_load_map_walkability():
    with tempfile.TemporaryDirectory() as tmp:
        _make_test_map(tmp)
        game_map = load_map(tmp)
        assert game_map.walkability[0][0, 0] == True
        assert game_map.walkability[0].shape == (32, 32)

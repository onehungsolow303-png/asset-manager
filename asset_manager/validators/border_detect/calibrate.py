"""Calibration engine — load/save/update technique weights."""

import json
from datetime import datetime
from pathlib import Path


def load_weights(path):
    """Load calibration weights from JSON file. Returns dict or None."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("technique_weights")
    except (json.JSONDecodeError, KeyError):
        return None


def save_calibration(path, technique_scores, old_weights):
    """Update calibration file with new scores using EMA smoothing."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    if path.exists():
        try:
            with open(path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, KeyError):
            pass

    new_weights = {}
    if old_weights is None:
        old_weights = {}
    default_weight = 1.0 / max(len(technique_scores), 1)
    weight_floor = 0.01

    for tid, scores in technique_scores.items():
        composite = scores.get("composite", 0.0)
        old_w = old_weights.get(tid, default_weight)
        new_w = 0.7 * old_w + 0.3 * composite
        new_weights[tid] = max(new_w, weight_floor)

    total = sum(new_weights.values())
    if total > 0:
        new_weights = {tid: w / total for tid, w in new_weights.items()}

    history = existing.get("history", [])
    history.append({"date": datetime.now().isoformat(), "techniques_scored": len(technique_scores)})
    history = history[-50:]

    calibration = {
        "version": 1,
        "last_updated": datetime.now().isoformat(),
        "technique_weights": new_weights,
        "technique_scores": {tid: s for tid, s in technique_scores.items()},
        "consensus_threshold": max(1, len(technique_scores) // 4),
        "history": history,
    }

    with open(path, "w") as f:
        json.dump(calibration, f, indent=2)

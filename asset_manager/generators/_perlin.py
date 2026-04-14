"""Perlin noise wrapper.

Mirrors the Unity-side ForeverEngine.Generation.Utility.PerlinNoise API used
by the archived C# generators:
- seed(int): set seed
- sample(x, y) -> float in approx [-1, 1]
- octave(x, y, octaves) -> float in approx [-1, 1]

Implementation note: the original plan called for the `noise` C-extension
library, but it doesn't have wheels for Python 3.14 on Windows. We use
`perlin-noise` (pure Python) instead. The two return slightly different
values for the same inputs but both mirror Ken Perlin's reference algorithm
closely enough that the visual output is indistinguishable.
"""

from __future__ import annotations

from perlin_noise import PerlinNoise

# Cached noise generators per (seed, octaves) so we don't reconstruct on every
# sample. Construction is cheap (~microseconds) but we sample millions of times
# during a single texture render.
_cache: dict[tuple[int, int], PerlinNoise] = {}
_current_seed: int = 0


def seed(s: int) -> None:
    """Set the seed for subsequent sample/octave calls."""
    global _current_seed
    _current_seed = s


def _get(octaves: int) -> PerlinNoise:
    key = (_current_seed, octaves)
    if key not in _cache:
        _cache[key] = PerlinNoise(octaves=octaves, seed=_current_seed)
    return _cache[key]


def sample(x: float, y: float) -> float:
    """Single-octave Perlin noise at (x, y), output in approx [-1, 1]."""
    return _get(1)([x, y])


def octave(x: float, y: float, octaves: int) -> float:
    """Multi-octave Perlin noise at (x, y), output in approx [-1, 1]."""
    return _get(octaves)([x, y])

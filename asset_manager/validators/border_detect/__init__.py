"""Multi-spectrum border detection — 40-technique ensemble with self-calibrating weights.

Both ensemble.py and pipeline.py depend on cv2/scipy for core image ops.
We lazy-tolerate missing deps here so that the package can still be imported
for smoke tests in a minimal environment. Callers (e.g. validator.py) wrap
their use in try/except and degrade gracefully.
"""
try:
    from .ensemble import detect_borders
except ImportError:  # cv2/scipy not installed
    detect_borders = None  # type: ignore[assignment]

try:
    from .pipeline import run_pipeline
except ImportError:  # cv2/scipy not installed
    run_pipeline = None  # type: ignore[assignment]

__all__ = ["detect_borders", "run_pipeline"]

"""Multi-spectrum border detection — 40-technique ensemble with self-calibrating weights."""
from border_detect.ensemble import detect_borders
from border_detect.pipeline import run_pipeline
__all__ = ["detect_borders", "run_pipeline"]

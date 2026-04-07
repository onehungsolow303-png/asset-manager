"""AssetValidator - composes border_detect + quality_metrics.

Public surface that selectors and the AI generation gateway call to
grade an asset before baking it into the library.

NOTE: The function names `border_pipeline.score_image` and `compute_metrics`
referenced below are GUESSED based on the spec. The actual salvaged files
may export different names. The validator catches AttributeError and
ImportError at the boundary and degrades gracefully to notes-only output,
so a name mismatch surfaces as a clear note rather than a crash. The first
follow-up that wires real validation through SmokeTest will reveal the
right names; update them then.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ValidationResult:
    passed: bool
    score: float
    border_score: float
    metric_scores: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class AssetValidator:
    def __init__(self, min_score: float = 0.5) -> None:
        self.min_score = min_score

    def validate(self, image_path: Path) -> ValidationResult:
        border_score = 0.0
        metric_scores: dict[str, float] = {}
        notes: list[str] = []

        try:
            from .border_detect import pipeline as border_pipeline  # type: ignore
            border_score = float(border_pipeline.score_image(str(image_path)))
        except (AttributeError, ImportError) as e:
            notes.append(f"border_detect.score_image not available: {e}")
        except Exception as e:
            notes.append(f"border_detect failed: {e}")

        try:
            from .quality_metrics import compute_metrics  # type: ignore
            metric_scores = compute_metrics(str(image_path))
        except (NameError, ImportError, AttributeError) as e:
            notes.append(f"compute_metrics not available: {e}")
        except Exception as e:
            notes.append(f"quality_metrics failed: {e}")

        score = border_score
        if metric_scores:
            score = (border_score + sum(metric_scores.values()) / len(metric_scores)) / 2

        return ValidationResult(
            passed=score >= self.min_score,
            score=score,
            border_score=border_score,
            metric_scores=metric_scores,
            notes=notes,
        )

"""AssetValidator — composes border_detect + quality_metrics.

Public surface that selectors and the AI generation gateway call to
grade an asset before baking it into the library.

Both underlying modules have heavy dependencies (cv2, scipy, skimage,
imagehash). The validator wraps every call in try/except so a missing
dep surfaces as a note rather than an import crash at module load.

Scoring strategy (single-image, no reference needed):
  * border_score: coverage of the v5+ pipeline alpha mask, i.e. the
    fraction of pixels the pipeline decided to keep. Healthy UI
    extractions land in ~0.2–0.7 range. We use coverage directly as a
    [0,1] score — not a quality score per se, but a real non-zero
    signal that the pipeline ran to completion.
  * metric_scores: derived from alpha_stats(), which reports the
    transparent/semi/opaque breakdown of an existing RGBA image. We
    turn that into a single 'opaque_fraction' metric in [0,1] so the
    score is a meaningful number rather than a raw dict.

The gateway calls AssetValidator().validate(path) and expects a
ValidationResult with `passed`, `score`, `notes`.
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

        # Pre-flight: file must exist
        if not image_path.exists():
            notes.append(f"file not found: {image_path}")
            return ValidationResult(
                passed=False,
                score=0.0,
                border_score=0.0,
                metric_scores={},
                notes=notes,
            )

        # ── Border score via v5+ pipeline coverage ──
        try:
            import cv2  # type: ignore

            from .border_detect.pipeline import run_pipeline

            img_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if img_bgr is None:
                notes.append(f"cv2.imread returned None for {image_path}")
            else:
                # run_pipeline returns a (H, W) uint8 alpha mask where
                # 255 = keep, 0 = remove. Coverage = fraction kept.
                alpha = run_pipeline(img_bgr)
                total = float(alpha.size)
                kept = float((alpha > 0).sum())
                border_score = kept / total if total > 0 else 0.0
        except ImportError as e:
            notes.append(f"border_detect unavailable (missing dep): {e}")
        except AttributeError as e:
            notes.append(f"border_detect.run_pipeline not found: {e}")
        except Exception as e:
            notes.append(f"border_detect failed: {e}")

        # ── Single-image quality metrics via alpha_stats ──
        # alpha_stats reports transparent/semi/opaque percentages for
        # the existing alpha channel of the image. We expose
        # opaque_fraction as a [0,1] metric.
        try:
            from PIL import Image

            from .quality_metrics import alpha_stats

            with Image.open(image_path) as pil_img:
                stats = alpha_stats(pil_img)
            metric_scores = {
                "opaque_fraction": round(stats["opaque"] / 100.0, 4),
                "semi_fraction": round(stats["semi"] / 100.0, 4),
                "transparent_fraction": round(stats["transparent"] / 100.0, 4),
            }
        except ImportError as e:
            notes.append(f"quality_metrics unavailable (missing dep): {e}")
        except (AttributeError, NameError) as e:
            notes.append(f"quality_metrics.alpha_stats not found: {e}")
        except Exception as e:
            notes.append(f"quality_metrics failed: {e}")

        # ── Combine ──
        # Single-number score: average of border_score and opaque_fraction
        # when both are available; otherwise whichever ran.
        opaque = metric_scores.get("opaque_fraction", 0.0)
        if border_score > 0 and metric_scores:
            score = (border_score + opaque) / 2
        elif border_score > 0:
            score = border_score
        elif metric_scores:
            score = opaque
        else:
            score = 0.0

        return ValidationResult(
            passed=score >= self.min_score,
            score=round(score, 4),
            border_score=round(border_score, 4),
            metric_scores=metric_scores,
            notes=notes,
        )

"""LoRA training scaffolding for the local Stable Diffusion path.

A LoRA (Low-Rank Adaptation) is a small file (~50-200 MB) that fine-tunes
a base Stable Diffusion model toward a specific visual style without
re-training the whole model. Once trained on a curated subset of your
D&D library, the LoRA can be loaded into local SD to generate NEW assets
that match your art style — for free, on your RTX 5090, in 5-15 seconds
per asset.

This module is SCAFFOLDING ONLY in this batch. The actual training run
needs:
  1. A curated dataset of 200-500 images at C:/Dev/.shared/lora_training/<lora_name>/
  2. The kohya_ss training scripts installed (or sd-scripts as alternative)
  3. The base SD model (SDXL or SD 1.5) available locally
  4. The user's explicit invocation of train()  (not autonomous)

Why kohya_ss / sd-scripts:
  These are the de-facto standard for SD LoRA training. They handle
  dataset preparation (caption generation, bucketing, augmentation),
  the training loop, sample generation, and LoRA file output. Both
  are MIT-licensed Python projects.

The training pipeline:

  1. Dataset prep
       - User curates 200-500 images representing the target style
       - prepare_dataset() copies them into the canonical training dir,
         strips metadata, resizes to a consistent base resolution (512
         or 1024), generates auto-captions via BLIP if missing
       - Outputs a manifest of what's in the dataset for reproducibility

  2. Training config
       - base_model: which Stable Diffusion checkpoint to fine-tune
                     (SDXL 1.0 for highest quality, SD 1.5 for speed)
       - rank: LoRA rank (8/16/32/64) — higher = more capacity, slower
       - learning_rate, batch_size, max_train_steps — standard knobs
       - sample_prompts: captions used to render preview images during
                          training so the user can monitor progress

  3. Training run
       - Spawned as a subprocess via train() (long-running, 30 min - 4 hours
         on RTX 5090 depending on dataset size and rank)
       - Stdout/stderr captured to a log file under .shared/lora_training/logs/
       - Periodic sample images saved alongside the LoRA checkpoint

  4. LoRA registration
       - On successful training, the .safetensors LoRA file lands at
         .shared/lora_training/<lora_name>/<lora_name>.safetensors
       - register_lora() adds it to the LoRA registry consumed by the
         local_sd generator gateway

This batch ships scaffolding for steps 1 and 4 plus the train() function
signature and dataset manifest. The actual SD/kohya_ss invocation is
deferred until the user has a curated subset and explicitly authorizes
the training run (it consumes 30+ minutes of GPU time).
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TRAINING_ROOT = Path("C:/Dev/.shared/lora_training")

# Image extensions accepted in the training dataset
_ACCEPTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class LoRATrainingConfig:
    """Knobs for a single training run.

    Defaults target the user's RTX 5090 + a small (~200-500 image)
    dataset. Tune up rank/steps for hero LoRAs, down for fast iteration.
    """

    lora_name: str
    base_model: str = "stabilityai/stable-diffusion-xl-base-1.0"
    rank: int = 16
    learning_rate: float = 1e-4
    batch_size: int = 1
    max_train_steps: int = 1500
    resolution: int = 1024
    sample_prompts: list[str] = field(
        default_factory=lambda: [
            "a fantasy creature token, top-down view, painterly, D&D style",
            "a wise old wizard, three-quarter portrait, fantasy art, painterly",
        ]
    )
    save_every_n_steps: int = 250


@dataclass
class DatasetManifest:
    """Records what's in a prepared training dataset, for reproducibility."""

    lora_name: str
    image_count: int
    image_paths: list[str]
    resolution: int
    captions_generated: int  # how many BLIP-auto captions were added


@dataclass
class TrainingResult:
    """Outcome of a training invocation."""

    success: bool
    lora_name: str
    lora_path: str | None = None
    log_path: str | None = None
    error: str | None = None


class LoRATrainer:
    """Manages dataset prep and training for LoRA fine-tunes.

    NOT a long-running daemon — instances are short-lived and bound to
    one training run. Construction is cheap; train() is the heavyweight
    method that subprocesses kohya_ss / sd-scripts.
    """

    def __init__(
        self,
        training_root: Path | None = None,
    ) -> None:
        self._root = training_root or DEFAULT_TRAINING_ROOT

    def dataset_dir(self, lora_name: str) -> Path:
        return self._root / lora_name / "dataset"

    def lora_dir(self, lora_name: str) -> Path:
        return self._root / lora_name / "checkpoints"

    def manifest_path(self, lora_name: str) -> Path:
        return self._root / lora_name / "dataset_manifest.json"

    def prepare_dataset(
        self,
        lora_name: str,
        source_images: list[Path],
        resolution: int = 1024,
    ) -> DatasetManifest:
        """Copy source images into the canonical training dataset dir.

        Idempotent: existing files in the dataset dir are left alone.
        Caption generation (BLIP) is a future enhancement — this batch
        only handles the file copy + manifest emission. The user can
        manually drop .txt caption files alongside each image now.

        Returns a DatasetManifest documenting what was prepared, which
        is also persisted to disk for reproducibility.
        """
        if not lora_name or not lora_name.replace("_", "").isalnum():
            raise ValueError(f"lora_name must be alphanumeric (with underscores): {lora_name!r}")

        target = self.dataset_dir(lora_name)
        target.mkdir(parents=True, exist_ok=True)

        copied: list[str] = []
        for src in source_images:
            src = Path(src)
            if not src.exists() or not src.is_file():
                logger.warning("[lora_trainer] skipping missing source: %s", src)
                continue
            if src.suffix.lower() not in _ACCEPTED_EXTENSIONS:
                logger.warning("[lora_trainer] skipping unrecognized: %s", src)
                continue
            dst = target / src.name
            if dst.exists():
                copied.append(str(dst))
                continue
            try:
                shutil.copy2(src, dst)
                copied.append(str(dst))
            except OSError as e:
                logger.warning("[lora_trainer] copy failed: %s -> %s: %s", src, dst, e)

        manifest = DatasetManifest(
            lora_name=lora_name,
            image_count=len(copied),
            image_paths=copied,
            resolution=resolution,
            captions_generated=0,  # not implemented yet
        )

        # Persist the manifest for reproducibility
        manifest_path = self.manifest_path(lora_name)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "lora_name": manifest.lora_name,
                    "image_count": manifest.image_count,
                    "resolution": manifest.resolution,
                    "captions_generated": manifest.captions_generated,
                    "image_paths": manifest.image_paths,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        logger.info(
            "[lora_trainer] prepared dataset %s: %d images at %s",
            lora_name,
            manifest.image_count,
            target,
        )
        return manifest

    def train(self, config: LoRATrainingConfig) -> TrainingResult:
        """Run a LoRA training pass.

        SCAFFOLDING ONLY this batch. The real implementation will:
          1. Verify kohya_ss / sd-scripts is installed and importable
          2. Verify the dataset is prepared (manifest exists, images present)
          3. Build a training arguments dict matching kohya_ss CLI shape
          4. Spawn a subprocess (kohya_ss is GPU-bound — long-running)
          5. Tee stdout/stderr to a log file
          6. On success, return a TrainingResult pointing at the .safetensors

        Until that lands, this method returns success=False with an
        error explaining what's still needed. The user can read the
        scaffolding to see what training would do without burning GPU
        time prematurely.
        """
        result = TrainingResult(
            success=False,
            lora_name=config.lora_name,
        )

        # Pre-flight checks (these are real, even though training itself
        # isn't wired up yet)
        dataset_dir = self.dataset_dir(config.lora_name)
        if not dataset_dir.exists():
            result.error = (
                f"dataset not prepared. Run prepare_dataset({config.lora_name!r}, "
                f"[curated images]) first."
            )
            return result

        manifest_path = self.manifest_path(config.lora_name)
        if not manifest_path.exists():
            result.error = f"dataset manifest missing: {manifest_path}"
            return result

        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            result.error = f"dataset manifest unreadable: {e}"
            return result

        if manifest_data.get("image_count", 0) < 50:
            result.error = (
                f"dataset has {manifest_data.get('image_count', 0)} images, "
                f"need at least 50 for a usable LoRA"
            )
            return result

        # Stub: real training would happen here. For now, we record the
        # config and return a clear "not yet implemented" error so the
        # caller knows the scaffolding is in place but not wired.
        result.error = (
            "LoRA training scaffolding is in place but the kohya_ss / "
            "sd-scripts integration is not yet implemented in this batch. "
            "Manual workaround: prepare the dataset via this module, then "
            f"run `accelerate launch sdxl_train_network.py --train_data_dir "
            f"{dataset_dir}` per kohya_ss docs. The trained LoRA file "
            f"belongs at {self.lora_dir(config.lora_name)}."
        )
        return result

    def list_loras(self) -> list[str]:
        """Return the names of all LoRAs that have a checkpoints/ folder.

        Used by the local_sd generator (future batch) to know which
        style LoRAs are available for loading at generation time.
        """
        if not self._root.exists():
            return []
        return sorted(
            [p.name for p in self._root.iterdir() if p.is_dir() and (p / "checkpoints").exists()]
        )

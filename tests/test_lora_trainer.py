"""Tests for the LoRA trainer scaffolding."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from asset_manager.pipeline.lora_trainer import (
    DatasetManifest,
    LoRATrainer,
    LoRATrainingConfig,
    TrainingResult,
)


def _make_image(path: Path) -> Path:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), (200, 100, 50)).save(path, format="PNG")
    return path


# ─── Construction ──────────────────────────────────────────────────


def test_dataset_dir_uses_lora_name(tmp_path):
    trainer = LoRATrainer(training_root=tmp_path)
    assert trainer.dataset_dir("test_lora") == tmp_path / "test_lora" / "dataset"
    assert trainer.lora_dir("test_lora") == tmp_path / "test_lora" / "checkpoints"


# ─── prepare_dataset ───────────────────────────────────────────────


def test_prepare_dataset_copies_images(tmp_path):
    trainer = LoRATrainer(training_root=tmp_path / "training")
    src_dir = tmp_path / "source"
    sources = [_make_image(src_dir / f"img_{i}.png") for i in range(5)]

    manifest = trainer.prepare_dataset("dnd_style", sources)

    assert manifest.image_count == 5
    assert manifest.lora_name == "dnd_style"
    target = trainer.dataset_dir("dnd_style")
    assert len(list(target.glob("*.png"))) == 5


def test_prepare_dataset_persists_manifest(tmp_path):
    trainer = LoRATrainer(training_root=tmp_path / "training")
    sources = [_make_image(tmp_path / f"img_{i}.png") for i in range(3)]

    trainer.prepare_dataset("dnd_style", sources)

    manifest_path = trainer.manifest_path("dnd_style")
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())
    assert data["lora_name"] == "dnd_style"
    assert data["image_count"] == 3


def test_prepare_dataset_skips_unrecognized_extensions(tmp_path):
    trainer = LoRATrainer(training_root=tmp_path / "training")
    img = _make_image(tmp_path / "good.png")
    bad = tmp_path / "notes.txt"
    bad.write_text("hi")
    missing = tmp_path / "ghost.png"  # never created

    manifest = trainer.prepare_dataset("dnd_style", [img, bad, missing])

    assert manifest.image_count == 1


def test_prepare_dataset_idempotent(tmp_path):
    trainer = LoRATrainer(training_root=tmp_path / "training")
    img = _make_image(tmp_path / "img.png")

    m1 = trainer.prepare_dataset("dnd", [img])
    m2 = trainer.prepare_dataset("dnd", [img])

    assert m1.image_count == 1
    assert m2.image_count == 1
    # No duplicates
    target = trainer.dataset_dir("dnd")
    assert len(list(target.glob("*.png"))) == 1


def test_prepare_dataset_rejects_invalid_lora_name(tmp_path):
    trainer = LoRATrainer(training_root=tmp_path / "training")
    with pytest.raises(ValueError, match="alphanumeric"):
        trainer.prepare_dataset("../evil/name", [])
    with pytest.raises(ValueError, match="alphanumeric"):
        trainer.prepare_dataset("name with spaces", [])


# ─── train (scaffolding state — not yet wired) ──────────────────────


def test_train_fails_without_dataset(tmp_path):
    trainer = LoRATrainer(training_root=tmp_path / "training")
    config = LoRATrainingConfig(lora_name="missing")
    result = trainer.train(config)
    assert result.success is False
    assert "dataset not prepared" in result.error


def test_train_fails_with_too_few_images(tmp_path):
    trainer = LoRATrainer(training_root=tmp_path / "training")
    sources = [_make_image(tmp_path / f"img_{i}.png") for i in range(3)]
    trainer.prepare_dataset("small_set", sources)

    config = LoRATrainingConfig(lora_name="small_set")
    result = trainer.train(config)
    assert result.success is False
    assert "at least 50" in result.error


def test_train_returns_not_implemented_for_valid_dataset(tmp_path):
    """Right now train() returns a clear 'scaffolding only' error when
    given a valid dataset. The real implementation arrives in a later
    batch when kohya_ss integration is wired."""
    trainer = LoRATrainer(training_root=tmp_path / "training")
    sources = [_make_image(tmp_path / f"img_{i}.png") for i in range(60)]
    trainer.prepare_dataset("good_set", sources)

    config = LoRATrainingConfig(lora_name="good_set")
    result = trainer.train(config)
    assert result.success is False
    assert "not yet implemented" in result.error


# ─── list_loras ────────────────────────────────────────────────────


def test_list_loras_empty_when_no_training_root(tmp_path):
    trainer = LoRATrainer(training_root=tmp_path / "nonexistent")
    assert trainer.list_loras() == []


def test_list_loras_finds_loras_with_checkpoints_dir(tmp_path):
    root = tmp_path / "training"
    (root / "lora_a" / "checkpoints").mkdir(parents=True)
    (root / "lora_b" / "checkpoints").mkdir(parents=True)
    (root / "lora_c").mkdir(parents=True)  # no checkpoints subdir — excluded

    trainer = LoRATrainer(training_root=root)
    loras = trainer.list_loras()
    assert "lora_a" in loras
    assert "lora_b" in loras
    assert "lora_c" not in loras

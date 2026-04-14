"""Local Stable Diffusion + LoRA generator stub.

The local SD path is the deterministic protocol's tier 4 (LOCAL_LORA_SD)
— effectively free per-generation on the user's RTX 5090, runs locally
without API keys, produces 2D images in the style learned by a LoRA
trained on the user's curated D&D library.

This module is the SCAFFOLDING for that path. It mirrors the gateway
interface (is_available, generate) but the actual SD inference is
deferred until the user has a trained LoRA. The methods all behave
correctly in the unavailable case so the source_decision router can
register this tier and have it gracefully no-op until the LoRA exists.

DETECTION:

The "available" check looks for one of three local SD installs in
priority order:

  1. Automatic1111 webui — most common, has an API at 127.0.0.1:7860
  2. ComfyUI — popular for advanced users, API at 127.0.0.1:8188
  3. Direct sd-scripts inference (kohya_ss) — for users who don't
     want to run a webui

Plus a trained LoRA in `.shared/lora_training/<name>/checkpoints/`.
Without a LoRA, the gateway returns is_available=False — there's no
point firing local SD if there's no style to apply.

USAGE (when wired):

  gw = LocalSDGateway(lora_name="dnd_style")
  if gw.is_available():
      out = gw.generate(
          prompt="a fantasy wolf in moonlight, top-down token, painterly",
          out_path=Path(".../baked/wolf.png"),
          width=512,
          height=512,
      )

DEFERRED:

  - Actual webui API client (Automatic1111 has /sdapi/v1/txt2img)
  - ComfyUI workflow JSON construction
  - sd-scripts subprocess invocation
  - LoRA strength + base model selection
  - Prompt enhancement via the style_bible preamble

These all land in a future batch when the user has a curated subset
and a trained LoRA. For now, generate() returns a clear
GatewayUnavailable so the router falls through to the next tier.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from asset_manager.gateway.base import GatewayUnavailable, GenerationGateway
from asset_manager.pipeline.lora_trainer import (
    DEFAULT_TRAINING_ROOT,
    LoRATrainer,
)

logger = logging.getLogger(__name__)

# Default ports for the most common local SD setups. Override via
# AUTOMATIC1111_API_URL / COMFYUI_API_URL env vars.
_DEFAULT_AUTOMATIC1111_URL = "http://127.0.0.1:7860"
_DEFAULT_COMFYUI_URL = "http://127.0.0.1:8188"


class LocalSDGateway(GenerationGateway):
    """Local Stable Diffusion + LoRA generator (stub).

    Construction does NOT probe the network — it just records what to
    look for. is_available() does the actual probe. This keeps the
    gateway cheap to construct in tests.
    """

    name = "local_sd"

    def __init__(
        self,
        lora_name: str | None = None,
        training_root: Path | None = None,
        automatic1111_url: str | None = None,
        comfyui_url: str | None = None,
    ) -> None:
        self._lora_name = lora_name
        self._trainer = LoRATrainer(training_root=training_root or DEFAULT_TRAINING_ROOT)
        self._automatic1111_url = (
            automatic1111_url
            or os.environ.get("AUTOMATIC1111_API_URL")
            or _DEFAULT_AUTOMATIC1111_URL
        )
        self._comfyui_url = comfyui_url or os.environ.get("COMFYUI_API_URL") or _DEFAULT_COMFYUI_URL

    @property
    def lora_name(self) -> str | None:
        return self._lora_name

    def is_available(self) -> bool:
        """Returns True iff:
            1. A LoRA name is configured AND
            2. The named LoRA has been trained (checkpoints/ exists) AND
            3. At least one local SD backend (Automatic1111 / ComfyUI)
               is reachable on its expected port

        Step 3 is currently a stub — we don't probe the network in this
        batch because the actual webui clients aren't wired yet. The
        gateway returns False until both the LoRA exists AND the
        backend is wired.
        """
        if not self._lora_name:
            return False
        loras = self._trainer.list_loras()
        if self._lora_name not in loras:
            return False
        # The webui probe is the next deferred piece. Until then, even
        # with a trained LoRA, the gateway reports unavailable so the
        # router cleanly falls through to the cloud tiers.
        return False

    def generate(self, prompt: str, out_path: Path, **kwargs: Any) -> Path:
        """Generate an image via local SD + LoRA.

        SCAFFOLDING ONLY in this batch. Always raises GatewayUnavailable
        with a clear message about what's still needed:
            - lora_name not set
            - LoRA not yet trained
            - webui backend not yet wired
        """
        if not self._lora_name:
            raise GatewayUnavailable(
                "LocalSDGateway requires lora_name in constructor. "
                "Pass the name of a trained LoRA from list_loras()."
            )

        loras = self._trainer.list_loras()
        if self._lora_name not in loras:
            raise GatewayUnavailable(
                f"LoRA {self._lora_name!r} not yet trained. "
                f"Available LoRAs: {loras or '(none)'}. "
                f"Train one via LoRATrainer.prepare_dataset() + train()."
            )

        # The actual SD inference is deferred to a future batch.
        raise GatewayUnavailable(
            "LocalSDGateway: webui backend integration is not yet "
            "implemented in this batch. Manual workaround: call "
            "Automatic1111's /sdapi/v1/txt2img API directly with the "
            f"trained LoRA {self._lora_name!r}, then drop the result "
            f"at {out_path} and the catalog auto-scan will pick it up."
        )

    def list_available_loras(self) -> list[str]:
        """Convenience: passes through to the LoRATrainer's list."""
        return self._trainer.list_loras()

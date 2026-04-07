"""Stable Diffusion gateway.

Talks to a local AUTOMATIC1111 web UI (or compatible /sdapi/v1/txt2img
endpoint) over HTTP. The gateway is "available" iff the configured
endpoint responds 200 to /sdapi/v1/sd-models within the timeout.

Configuration via environment variables:
    SD_API_BASE_URL  default http://127.0.0.1:7860
    SD_API_TIMEOUT   default 60.0  (txt2img can be slow)
    SD_DEFAULT_STEPS default 20
    SD_DEFAULT_WIDTH  default 512
    SD_DEFAULT_HEIGHT default 512

To enable in production:
    1. Run AUTOMATIC1111 locally on port 7860 (or set SD_API_BASE_URL)
    2. Make sure --api is in its launch args
    3. The gateway auto-detects on next /generate request

Spec: 2026-04-06-three-module-consolidation-design.md §6.2 (asset gateway)
"""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from .base import GatewayUnavailable, GenerationGateway

logger = logging.getLogger(__name__)


class StableDiffusionGateway(GenerationGateway):
    name = "stable_diffusion"

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._base_url = (base_url or os.environ.get("SD_API_BASE_URL", "http://127.0.0.1:7860")).rstrip("/")
        self._timeout = float(timeout or os.environ.get("SD_API_TIMEOUT", "60.0"))
        self._default_steps = int(os.environ.get("SD_DEFAULT_STEPS", "20"))
        self._default_width = int(os.environ.get("SD_DEFAULT_WIDTH", "512"))
        self._default_height = int(os.environ.get("SD_DEFAULT_HEIGHT", "512"))

    def is_available(self) -> bool:
        """Cheap reachability probe — does GET /sdapi/v1/sd-models return 200?"""
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(f"{self._base_url}/sdapi/v1/sd-models")
            return resp.status_code == 200
        except httpx.RequestError:
            return False

    def generate(self, prompt: str, out_path: Path, **kwargs: Any) -> Path:
        steps = int(kwargs.get("steps", self._default_steps))
        width = int(kwargs.get("width", self._default_width))
        height = int(kwargs.get("height", self._default_height))
        negative_prompt = str(kwargs.get("negative_prompt", ""))
        seed = int(kwargs.get("seed", -1))

        payload: dict[str, Any] = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "steps": steps,
            "width": width,
            "height": height,
            "seed": seed,
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(f"{self._base_url}/sdapi/v1/txt2img", json=payload)
        except httpx.RequestError as e:
            raise GatewayUnavailable(f"SD endpoint unreachable: {e}") from e

        if resp.status_code != 200:
            raise GatewayUnavailable(
                f"SD endpoint returned {resp.status_code}: {resp.text[:200]}"
            )

        body = resp.json()
        images = body.get("images") or []
        if not images:
            raise GatewayUnavailable("SD response had no images")

        # AUTOMATIC1111 returns each image as a base64-encoded PNG
        try:
            png_bytes = base64.b64decode(images[0])
        except (ValueError, TypeError) as e:
            raise GatewayUnavailable(f"SD response image not base64: {e}") from e

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(png_bytes)
        return out_path

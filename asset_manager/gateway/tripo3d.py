"""Tripo3D gateway — image-to-3D mesh generation.

Tripo3D produces a textured 3D mesh from a single 2D image (or text
prompt). The output GLB can be imported directly into Unity via Tripo's
DCC Bridge OR rendered to 2D sprites via Blender headless. This gateway
wraps the Tripo3D HTTP API following the same pattern as scenario.py:

  - Cheap is_available() probe based on TRIPO_API_KEY env var
  - Async job submission + poll-until-done
  - Returns a Path to the downloaded GLB
  - Raises GatewayUnavailable on any failure (caller decides fallback)

Configuration via environment variables:
    TRIPO_API_KEY      required — your Tripo3D API key from
                        https://platform.tripo3d.ai/api-keys
    TRIPO_API_BASE_URL default https://api.tripo3d.ai/v2/openapi
    TRIPO_TIMEOUT      default 300.0  (3D generation is slower than 2D)

Pricing context (as of 2026-04 — verify before high-volume use):
    Free tier: 100 free credits per month
    Image-to-3D: typically 1 credit per generation
    Text-to-3D: typically 5 credits per generation
    Cache hit cost: $0 — only the FIRST generation pays

The gateway is "available" iff TRIPO_API_KEY is set. We do NOT make a
network probe in is_available() because Tripo's status endpoint is
slower than ideal and the probe would dominate /generate latency. The
real availability check happens on the actual job submission.

Why GLB output instead of OBJ/FBX:
    GLB is the modern web-3D format, single-file (textures embedded),
    well-supported by Unity 6 native importer, and Blender's bpy can
    load it directly without extra add-ons. Tripo3D's API supports GLB
    output natively.

Cache strategy (used by source_decision.py):
    The Tripo3D gateway is the most expensive tier in the deterministic
    protocol — only invoked when cheaper tiers (cache, library, local
    procedural, local LoRA) all miss. Every successful generation is
    cached as a manifest entry with cost_usd populated, so future
    requests for the same semantic asset never re-bill.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx

from .base import GatewayUnavailable, GenerationGateway

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.tripo3d.ai/v2/openapi"


class Tripo3DGateway(GenerationGateway):
    name = "tripo3d"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("TRIPO_API_KEY")
        self._base_url = (
            base_url or os.environ.get("TRIPO_API_BASE_URL", DEFAULT_BASE_URL)
        ).rstrip("/")
        self._timeout = float(timeout or os.environ.get("TRIPO_TIMEOUT", "300.0"))

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def is_available(self) -> bool:
        """Cheap availability check — does the API key exist?

        We deliberately do NOT make a network call here. Tripo's API
        ping is slower than the rest of the gateway tier and would
        dominate /generate latency. The real failure mode (bad key,
        network down, no credits) surfaces during the actual job
        submission as a GatewayUnavailable exception.
        """
        return bool(self._api_key)

    def generate(self, prompt: str, out_path: Path, **kwargs: Any) -> Path:
        """Generate a 3D mesh and download it to out_path.

        Two modes via kwargs:
            mode="text":  pure text-to-3D using `prompt` as the input
            mode="image": image-to-3D using kwargs["image_path"] as the
                          source PNG; `prompt` becomes a style hint
                          appended to the request

        Common kwargs:
            mode               text | image (default: text)
            image_path         Path to source PNG (required when mode=image)
            style              optional style preset (e.g. "fantasy",
                               "cartoon", "realistic") — Tripo defaults
                               work fine for D&D content
            texture            bool, default True — generate PBR textures
            pbr                bool, default True — emit PBR materials
            face_limit         int, default 0 (let Tripo decide) — cap
                               polygon count for low-poly outputs

        Returns the path on success. Raises GatewayUnavailable on:
            - missing API key
            - missing image_path when mode=image
            - submission HTTP error
            - job timeout (default 4 minutes)
            - job state ends in failed/cancelled
            - download HTTP error
        """
        if not self._api_key:
            raise GatewayUnavailable("TRIPO_API_KEY not set")

        mode = str(kwargs.get("mode", "text"))
        if mode not in ("text", "image"):
            raise GatewayUnavailable(f"unsupported mode: {mode!r}")

        try:
            with httpx.Client(timeout=self._timeout) as client:
                # ── Step 1: submit the generation task ──
                if mode == "image":
                    image_path = kwargs.get("image_path")
                    if not image_path:
                        raise GatewayUnavailable(
                            "mode=image requires kwargs['image_path']"
                        )
                    image_path = Path(image_path)
                    if not image_path.exists():
                        raise GatewayUnavailable(
                            f"image_path does not exist: {image_path}"
                        )
                    # Tripo's image-to-3D expects either a public URL or
                    # an uploaded file token. We upload first.
                    upload_token = self._upload_image(client, image_path)
                    submit_payload: dict[str, Any] = {
                        "type": "image_to_model",
                        "file": {"type": "image", "file_token": upload_token},
                        "prompt": prompt,
                    }
                else:
                    submit_payload = {
                        "type": "text_to_model",
                        "prompt": prompt,
                    }

                # Optional knobs the caller can pass through
                if (style := kwargs.get("style")) is not None:
                    submit_payload["style"] = style
                if (texture := kwargs.get("texture")) is not None:
                    submit_payload["texture"] = bool(texture)
                if (pbr := kwargs.get("pbr")) is not None:
                    submit_payload["pbr"] = bool(pbr)
                if (face_limit := kwargs.get("face_limit")) is not None:
                    submit_payload["face_limit"] = int(face_limit)

                submit = client.post(
                    f"{self._base_url}/task",
                    json=submit_payload,
                    headers=self._headers(),
                )
                if submit.status_code not in (200, 201):
                    raise GatewayUnavailable(
                        f"submit returned {submit.status_code}: "
                        f"{submit.text[:200]}"
                    )
                body = submit.json()
                task_id = (
                    body.get("data", {}).get("task_id")
                    or body.get("task_id")
                )
                if not task_id:
                    raise GatewayUnavailable(f"submit missing task_id: {body}")

                # ── Step 2: poll until done ──
                model_url = self._poll_until_done(client, task_id)

                # ── Step 3: download the GLB ──
                dl = client.get(model_url, timeout=self._timeout)
                if dl.status_code != 200:
                    raise GatewayUnavailable(
                        f"GLB download returned {dl.status_code}"
                    )
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(dl.content)
                return out_path

        except httpx.RequestError as e:
            raise GatewayUnavailable(f"tripo3d unreachable: {e}") from e

    def _upload_image(self, client: httpx.Client, image_path: Path) -> str:
        """Upload a local image and return the file_token Tripo references."""
        with open(image_path, "rb") as f:
            files = {"file": (image_path.name, f, "image/png")}
            # Upload endpoint takes multipart/form-data, NOT JSON, so we
            # build a separate header set without Content-Type.
            upload_headers = {"Authorization": f"Bearer {self._api_key}"}
            resp = client.post(
                f"{self._base_url}/upload",
                files=files,
                headers=upload_headers,
            )
        if resp.status_code != 200:
            raise GatewayUnavailable(
                f"upload returned {resp.status_code}: {resp.text[:200]}"
            )
        body = resp.json()
        token = (
            body.get("data", {}).get("file_token")
            or body.get("file_token")
        )
        if not token:
            raise GatewayUnavailable(f"upload response missing file_token: {body}")
        return token

    def _poll_until_done(self, client: httpx.Client, task_id: str) -> str:
        """Poll the task endpoint until status=success and return the
        downloadable model URL. Raises on timeout or failure."""
        deadline = time.monotonic() + min(self._timeout, 240.0)
        while time.monotonic() < deadline:
            poll = client.get(
                f"{self._base_url}/task/{task_id}",
                headers=self._headers(),
            )
            if poll.status_code != 200:
                raise GatewayUnavailable(
                    f"poll returned {poll.status_code}: {poll.text[:200]}"
                )
            body = poll.json().get("data", {}) or poll.json()
            status = body.get("status")
            if status == "success":
                model = body.get("output", {}).get("model")
                if not model:
                    raise GatewayUnavailable(
                        f"task success but no model URL: {body}"
                    )
                return model
            if status in ("failed", "cancelled", "banned"):
                raise GatewayUnavailable(f"task ended in status: {status}")
            time.sleep(2.0)

        raise GatewayUnavailable(f"task {task_id} timed out after {self._timeout}s")

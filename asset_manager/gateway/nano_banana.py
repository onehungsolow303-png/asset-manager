"""Nano Banana gateway — Google Gemini 2.5 Flash Image API.

"Nano Banana" is the colloquial name for Google's Gemini 2.5 Flash Image
model — released August 2025 — designed for fast image editing and
generation while preserving subject identity. It's the right tool for
turning a Roll20 marketplace asset into a derivative work that's both
substantially modified (license-safer) AND in your target style.

Two primary modes for the Forever engine pipeline:

  1. text_to_image — generate a new image from a prompt alone. Same role
     as Stable Diffusion / DALL-E. Used when no source asset exists.

  2. image_to_image (the killer feature) — take a source PNG plus an
     edit prompt and produce a modified version. Preserves the subject's
     identity (pose, character, layout) while applying the requested
     changes (palette shift, style transfer, prop swap, lighting change).
     This is the "nano banana to slightly change them" workflow you
     described — turn a Roll20 dwarf into your dwarf.

Configuration via environment variables:
    GEMINI_API_KEY    required — your Google AI Studio API key from
                       https://aistudio.google.com/apikey
    GEMINI_API_BASE   default https://generativelanguage.googleapis.com/v1beta
    GEMINI_TIMEOUT    default 60.0 (image edits are fast — usually <30s)
    GEMINI_MODEL_ID   default gemini-2.5-flash-image (the nano banana model)

Pricing context (as of 2026-04 — verify before high-volume use):
    Free tier: substantial daily quota (currently 1500 image edits/day)
    Paid tier: ~$0.039 per image generation (0.039 / 1000 image tokens)
    Cache hit cost: $0 — only the FIRST generation pays

The gateway is "available" iff GEMINI_API_KEY is set. Same cheap-probe
pattern as the Tripo3D gateway: no network call in is_available() to
keep /generate latency fast.
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

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL_ID = "gemini-2.5-flash-image"


class NanoBananaGateway(GenerationGateway):
    name = "nano_banana"

    def __init__(
        self,
        api_key: str | None = None,
        model_id: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._model_id = model_id or os.environ.get("GEMINI_MODEL_ID", DEFAULT_MODEL_ID)
        self._base_url = (base_url or os.environ.get("GEMINI_API_BASE", DEFAULT_BASE_URL)).rstrip(
            "/"
        )
        self._timeout = float(timeout or os.environ.get("GEMINI_TIMEOUT", "60.0"))

    def is_available(self) -> bool:
        """Cheap availability — does the API key exist?

        Same rationale as Tripo3D: no network probe to keep /generate
        latency fast. Real failures surface during the actual call.
        """
        return bool(self._api_key)

    def generate(self, prompt: str, out_path: Path, **kwargs: Any) -> Path:
        """Generate or edit an image and write the result to out_path.

        Modes:
            mode="text"  — text-to-image, prompt is the only input.
            mode="image" — image-to-image edit, requires kwargs[image_path].
                            The source image is preserved/identified, the
                            prompt describes the edit ("change armor to
                            blue and gold, painterly style").

        Returns out_path on success. Raises GatewayUnavailable on:
            - missing API key
            - missing image_path when mode=image
            - HTTP error from the Gemini API
            - response missing the inline image data
        """
        if not self._api_key:
            raise GatewayUnavailable("GEMINI_API_KEY not set")

        mode = str(kwargs.get("mode", "text"))
        if mode not in ("text", "image"):
            raise GatewayUnavailable(f"unsupported mode: {mode!r}")

        # Build the parts list — text always present, image only in
        # image-to-image mode. The Gemini Image API uses a content/parts
        # structure where each part is either {text: ...} or
        # {inlineData: {mimeType, data}} for binary inputs.
        parts: list[dict[str, Any]] = [{"text": prompt}]

        if mode == "image":
            image_path = kwargs.get("image_path")
            if not image_path:
                raise GatewayUnavailable("mode=image requires kwargs['image_path']")
            image_path = Path(image_path)
            if not image_path.exists():
                raise GatewayUnavailable(f"image_path does not exist: {image_path}")
            mime = _guess_mime(image_path)
            encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
            parts.append(
                {
                    "inlineData": {
                        "mimeType": mime,
                        "data": encoded,
                    },
                }
            )

        body: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": parts,
                }
            ],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
            },
        }

        url = f"{self._base_url}/models/{self._model_id}:generateContent?key={self._api_key}"

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(
                    url,
                    json=body,
                    headers={"Content-Type": "application/json"},
                )
        except httpx.RequestError as e:
            raise GatewayUnavailable(f"gemini unreachable: {e}") from e

        if resp.status_code != 200:
            raise GatewayUnavailable(f"gemini returned {resp.status_code}: {resp.text[:200]}")

        # Walk the response for the first inline image part. Gemini's
        # response schema nests the image bytes deeply:
        #   candidates[0].content.parts[N].inlineData.data
        try:
            data = resp.json()
        except ValueError as e:
            raise GatewayUnavailable(f"gemini response not JSON: {e}") from e

        image_bytes = _extract_inline_image(data)
        if image_bytes is None:
            raise GatewayUnavailable(
                f"gemini response missing inline image data: {str(data)[:300]}"
            )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(image_bytes)
        return out_path


def _guess_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "application/octet-stream")


def _extract_inline_image(response: dict[str, Any]) -> bytes | None:
    """Walk the Gemini response candidates and pull out the first inline
    image data, returning the raw image bytes (already base64-decoded).

    Returns None if no image part is found anywhere in the response,
    which the caller turns into a GatewayUnavailable.
    """
    candidates = response.get("candidates") or []
    for cand in candidates:
        parts = (cand.get("content") or {}).get("parts") or []
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data") or {}
            data_b64 = inline.get("data")
            if data_b64:
                try:
                    return base64.b64decode(data_b64)
                except (ValueError, TypeError):
                    continue
    return None

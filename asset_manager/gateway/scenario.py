"""Scenario.gg gateway.

Talks to the Scenario.gg cloud API for style-consistent game asset
generation. The gateway is "available" iff SCENARIO_API_KEY is set in
the environment AND the API responds 200 to /generate-meta within the
timeout (the actual job submission is async; this is just a probe).

Configuration via environment variables:
    SCENARIO_API_KEY      required — your scenario.gg API key
    SCENARIO_API_BASE_URL default https://api.cloud.scenario.com/v1
    SCENARIO_TIMEOUT      default 120.0  (cloud generation is slow)
    SCENARIO_MODEL_ID     required for actual generation — pick a trained model from your account

To enable in production:
    1. Sign up at scenario.gg and create an API key
    2. Train or pick a model; copy its model_id
    3. export SCENARIO_API_KEY=...
    4. export SCENARIO_MODEL_ID=...
    5. The gateway auto-detects on next /generate request

Spec: 2026-04-06-three-module-consolidation-design.md §6.2 (asset gateway)
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

DEFAULT_BASE_URL = "https://api.cloud.scenario.com/v1"


class ScenarioGateway(GenerationGateway):
    name = "scenario"

    def __init__(
        self,
        api_key: str | None = None,
        model_id: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("SCENARIO_API_KEY")
        self._model_id = model_id or os.environ.get("SCENARIO_MODEL_ID")
        self._base_url = (
            base_url or os.environ.get("SCENARIO_API_BASE_URL", DEFAULT_BASE_URL)
        ).rstrip("/")
        self._timeout = float(timeout or os.environ.get("SCENARIO_TIMEOUT", "120.0"))

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Basic {self._api_key}",
            "Content-Type": "application/json",
        }

    def is_available(self) -> bool:
        """Cheap reachability probe — does the API key resolve?

        We don't poll model state on every request; the GET on /models
        is cheap and tells us both that the network reaches scenario.gg
        and that the API key is valid.
        """
        if not self._api_key:
            return False
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(f"{self._base_url}/models", headers=self._headers())
            return resp.status_code == 200
        except httpx.RequestError:
            return False

    def generate(self, prompt: str, out_path: Path, **kwargs: Any) -> Path:
        if not self._api_key:
            raise GatewayUnavailable("SCENARIO_API_KEY not set")
        if not self._model_id and not kwargs.get("model_id"):
            raise GatewayUnavailable("SCENARIO_MODEL_ID not set (and no model_id in kwargs)")

        model_id = str(kwargs.get("model_id", self._model_id))
        width = int(kwargs.get("width", 512))
        height = int(kwargs.get("height", 512))
        num_samples = int(kwargs.get("num_samples", 1))

        submit_payload: dict[str, Any] = {
            "prompt": prompt,
            "modelId": model_id,
            "width": width,
            "height": height,
            "numSamples": num_samples,
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                # Submit
                submit = client.post(
                    f"{self._base_url}/generate/txt2img",
                    json=submit_payload,
                    headers=self._headers(),
                )
                if submit.status_code != 200:
                    raise GatewayUnavailable(
                        f"submit returned {submit.status_code}: {submit.text[:200]}"
                    )
                job = submit.json()
                job_id = job.get("job", {}).get("jobId") or job.get("jobId")
                if not job_id:
                    raise GatewayUnavailable(f"submit response missing jobId: {job}")

                # Poll until job done or we hit a soft timeout (90s)
                deadline = time.monotonic() + 90.0
                while time.monotonic() < deadline:
                    poll = client.get(
                        f"{self._base_url}/jobs/{job_id}",
                        headers=self._headers(),
                    )
                    if poll.status_code != 200:
                        raise GatewayUnavailable(
                            f"poll returned {poll.status_code}: {poll.text[:200]}"
                        )
                    job_state = poll.json().get("job", {})
                    status = job_state.get("status")
                    if status == "success":
                        assets = job_state.get("metadata", {}).get("assetIds") or []
                        if not assets:
                            raise GatewayUnavailable("job success but no assetIds")
                        asset_id = assets[0]
                        # Download
                        dl = client.get(
                            f"{self._base_url}/assets/{asset_id}",
                            headers=self._headers(),
                        )
                        if dl.status_code != 200:
                            raise GatewayUnavailable(f"asset download returned {dl.status_code}")
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        out_path.write_bytes(dl.content)
                        return out_path
                    if status in ("failure", "rejected"):
                        raise GatewayUnavailable(f"job ended in status: {status}")
                    time.sleep(1.0)

                raise GatewayUnavailable(f"job {job_id} timed out after 90s")
        except httpx.RequestError as e:
            raise GatewayUnavailable(f"scenario.gg unreachable: {e}") from e

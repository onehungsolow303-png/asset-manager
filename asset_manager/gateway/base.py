"""Generation gateway ABC.

Every AI image generation gateway implements `generate(prompt, out_path)`
and reports availability via `is_available()`. The bridge dispatches to
whichever gateway the user has configured + that reports available; if
none are available, /generate returns the existing procedural fallback.
"""
from __future__ import annotations

import abc
from pathlib import Path
from typing import Any


class GatewayUnavailable(Exception):
    """Raised when a gateway can't service a request (missing creds,
    server unreachable, model not loaded, etc.)."""


class GenerationGateway(abc.ABC):
    name: str = "gateway"

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Return True if this gateway is configured and reachable.

        Should be cheap (no network call). The bridge calls this on every
        /generate request to decide whether to dispatch.
        """
        ...

    @abc.abstractmethod
    def generate(self, prompt: str, out_path: Path, **kwargs: Any) -> Path:
        """Generate an image for `prompt` and write it to `out_path`.

        Returns the path on success. Raises GatewayUnavailable on any
        failure (missing creds, network error, model not loaded). The
        bridge catches the exception and falls back to procedural
        generation or returns a structured error to the caller.
        """
        ...

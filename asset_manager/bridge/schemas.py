"""Pydantic models for the Asset Manager HTTP bridge.

Mirrors C:/Dev/.shared/schemas/selection.schema.json plus a few
request/response wrappers specific to this service.

Hardening: every model uses ``extra="forbid"`` so unknown fields raise
a validation error instead of silently drifting from the JSON schemas,
and ``schema_version`` is a ``Literal["1.0.0"]`` so wrong-version
payloads are rejected at the boundary. This was added after the
Phase 1 reviewer caught pydantic drift from the schemas in
``C:/Dev/.shared/schemas/``.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class AssetSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    kind: str
    biome: Optional[str] = None
    theme: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    allow_ai_generation: bool = False


class AssetSelectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    found: bool
    asset_id: Optional[str] = None
    path: Optional[str] = None
    manifest: Optional[dict[str, Any]] = None
    notes: list[str] = Field(default_factory=list)


class GenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    kind: str
    prompt: str
    style: Optional[str] = None
    constraints: dict[str, Any] = Field(default_factory=dict)


class GenerationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    accepted: bool
    asset_id: Optional[str] = None
    path: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class CatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    count: int
    assets: list[dict[str, Any]]

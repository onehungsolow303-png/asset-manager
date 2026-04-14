"""Pydantic models for the Asset Manager HTTP bridge.

The schema-backed class (`AssetSelectionRequest`) is imported from the
generated module that mirrors `C:/Dev/.shared/schemas/selection.schema.json`.
The four service-internal wrappers (`AssetSelectionResponse`,
`GenerationRequest`, `GenerationResponse`, `CatalogResponse`) are
Asset Manager-specific — they have no entry in `.shared/schemas/` because
no other service produces or consumes them in those exact shapes — so they
stay hand-written here.

Hardening for the schema-backed class (extra="forbid", Literal const pinning)
is applied centrally by `.shared/codegen/python_gen.py`. Hardening for the
local wrappers is applied here for consistency.

Update flow when contracts change:
  1. Edit the JSON schema in C:/Dev/.shared/schemas/
  2. cd C:/Dev/.shared && python codegen/python_gen.py --out codegen/golden_python.py
  3. cp C:/Dev/.shared/codegen/golden_python.py C:/Dev/Asset Manager/asset_manager/bridge/_generated_schemas.py
  4. Run pytest tests/
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Re-export the schema-backed class under the name callers already use.
# This is the SOURCE OF TRUTH — never redefine it locally.
from asset_manager.bridge._generated_schemas import (  # noqa: F401
    AssetSelectionRequest,
)


class AssetSelectionResponse(BaseModel):
    """Asset Manager-internal: response to /select."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    found: bool
    asset_id: str | None = None
    path: str | None = None
    manifest: dict[str, Any] | None = None
    notes: list[str] = Field(default_factory=list)


class GenerationRequest(BaseModel):
    """Asset Manager-internal: request to /generate."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    kind: str
    prompt: str
    style: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)


class GenerationResponse(BaseModel):
    """Asset Manager-internal: response to /generate."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    accepted: bool
    asset_id: str | None = None
    path: str | None = None
    notes: list[str] = Field(default_factory=list)


class CatalogResponse(BaseModel):
    """Asset Manager-internal: response to /catalog."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    count: int
    assets: list[dict[str, Any]]

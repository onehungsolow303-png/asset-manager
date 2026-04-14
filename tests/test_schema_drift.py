"""Contract drift detector.

Compares the vendored `asset_manager/bridge/_generated_schemas.py` against
what `.shared/codegen/python_gen.py` would produce TODAY. If they differ,
the JSON schemas in `.shared/schemas/` have moved since the vendored
copy was last refreshed and someone needs to re-vendor:

    cp C:/Dev/.shared/codegen/golden_python.py \\
       asset_manager/bridge/_generated_schemas.py

The test skips when `.shared/codegen/python_gen.py` isn't reachable
(e.g., CI runs on a hosted runner without the cross-repo checkout).
This means it's a guard for local dev and for CI configurations that
explicitly check out `.shared` as a sibling — not a hard gate that
breaks isolated runs.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_CANDIDATE_SHARED_ROOTS = [
    Path("C:/Dev/.shared"),
    Path(__file__).resolve().parent.parent.parent / ".shared",
    Path(__file__).resolve().parent.parent.parent.parent / ".shared",
]


def _find_shared_codegen() -> Path | None:
    for root in _CANDIDATE_SHARED_ROOTS:
        candidate = root / "codegen" / "python_gen.py"
        if candidate.exists():
            return candidate
    return None


def test_vendored_schemas_match_shared_codegen():
    codegen = _find_shared_codegen()
    if codegen is None:
        pytest.skip(
            "C:/Dev/.shared/codegen/python_gen.py not reachable; skipping contract-drift check."
        )

    vendored = (
        Path(__file__).resolve().parent.parent
        / "asset_manager"
        / "bridge"
        / "_generated_schemas.py"
    )
    assert vendored.exists(), f"vendored schemas missing at {vendored}"

    result = subprocess.run(
        [sys.executable, str(codegen)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"python_gen.py failed (returncode={result.returncode}): {result.stderr}")

    fresh = result.stdout
    vendored_text = vendored.read_text()

    if fresh != vendored_text:
        from difflib import unified_diff

        diff = "".join(
            unified_diff(
                vendored_text.splitlines(keepends=True),
                fresh.splitlines(keepends=True),
                fromfile="vendored _generated_schemas.py",
                tofile="freshly generated from .shared/",
                n=3,
            )
        )
        pytest.fail(
            "Contract drift detected. The vendored _generated_schemas.py "
            "is stale relative to .shared/codegen/python_gen.py output. "
            "Re-vendor with:\n"
            "  cp C:/Dev/.shared/codegen/golden_python.py "
            "asset_manager/bridge/_generated_schemas.py\n\n"
            f"Diff (first 40 lines):\n{''.join(diff.splitlines(keepends=True)[:40])}"
        )

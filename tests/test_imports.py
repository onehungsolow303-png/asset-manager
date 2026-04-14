"""Smoke test: import every module under asset_manager/.

Catches bare-import regressions (e.g., a file that uses 'from base_agent import X'
instead of 'from .base_agent import X'). The verify gate caught nothing in Phase 2
because the FastAPI bridge happened to never touch the broken modules.

Some modules under asset_manager/validators/border_detect/ require heavy image
deps (cv2, scipy). In a minimal venv those raise ModuleNotFoundError at import
time — that's an environment problem, not a bare-import regression. We skip
those specific modules via a known list and still catch every OTHER import bug.
"""

import importlib
import pkgutil

import pytest

import asset_manager

# Modules that require cv2/scipy/etc. at import time. Skipped when the dep
# is missing (so CI minimal venv passes), still exercised when the dep is
# available (so real regressions are caught).
_RUNTIME_DEP_MODULES = {
    "asset_manager.validators.border_detect",
    "asset_manager.validators.border_detect.ensemble",
    "asset_manager.validators.border_detect.pipeline",
    "asset_manager.validators.border_detect.preprocess",
    "asset_manager.validators.border_detect.calibrate",
    "asset_manager.validators.border_detect.techniques",
    "asset_manager.validators.border_detect.techniques.adaptive",
    "asset_manager.validators.border_detect.techniques.color",
    "asset_manager.validators.border_detect.techniques.edge",
    "asset_manager.validators.border_detect.techniques.gradient",
    "asset_manager.validators.border_detect.techniques.morphological",
    "asset_manager.validators.border_detect.techniques.quantization",
    "asset_manager.validators.border_detect.techniques.statistical",
    "asset_manager.validators.border_detect.techniques.structural",
    "asset_manager.validators.border_detect.techniques.texture",
}


def _all_module_names():
    return [
        m.name for m in pkgutil.walk_packages(asset_manager.__path__, asset_manager.__name__ + ".")
    ]


@pytest.mark.parametrize("module_name", _all_module_names())
def test_module_imports(module_name):
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        # Tolerate a missing runtime dep (cv2/scipy) for the known border_detect
        # modules. Any other missing module means a real bare-import bug.
        missing = getattr(e, "name", "")
        if module_name in _RUNTIME_DEP_MODULES and missing in {
            "cv2",
            "scipy",
            "skimage",
            "imagehash",
        }:
            pytest.skip(f"{module_name} requires {missing} (not installed in this venv)")
        raise

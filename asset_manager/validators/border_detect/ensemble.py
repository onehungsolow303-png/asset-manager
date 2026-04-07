"""Ensemble combiner — weighted voting + consensus for border detection."""
import time
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

from border_detect.preprocess import preprocess
from border_detect.techniques import get_all_techniques

# Images above this pixel count get downsampled before processing
MAX_PIXELS = 2_000_000  # ~1920x1040


def detect_borders(img_bgr, mode="general", calibration_weights=None):
    """Run all 40 techniques and combine into a single border confidence map.

    Images larger than MAX_PIXELS are downsampled for technique processing,
    then the final border map is upscaled back to original dimensions.
    """
    start = time.time()
    orig_h, orig_w = img_bgr.shape[:2]
    total_pixels = orig_h * orig_w

    # Downsample large images for processing speed
    scale = 1.0
    working_img = img_bgr
    if total_pixels > MAX_PIXELS:
        scale = (MAX_PIXELS / total_pixels) ** 0.5
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        working_img = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
        print(f"  [Ensemble] Downsampled {orig_w}x{orig_h} -> {new_w}x{new_h} ({scale:.2f}x)")

    preprocessed = preprocess(working_img)
    techniques = get_all_techniques()
    h, w = preprocessed["height"], preprocessed["width"]

    # Run all techniques in parallel
    results = {}
    with ThreadPoolExecutor() as pool:
        futures = {pool.submit(_run_one, tid, fn, preprocessed): tid
                   for tid, fn in techniques}
        for future in futures:
            tid = futures[future]
            try:
                results[tid] = future.result(timeout=30)
            except Exception as e:
                print(f"  Technique {tid} failed: {e}")
                results[tid] = np.zeros((h, w), dtype=np.float32)

    # Load weights
    if calibration_weights is None:
        calibration_weights = {}
    default_weight = 1.0 / len(techniques)
    weights = {tid: calibration_weights.get(tid, default_weight) for tid, _ in techniques}

    # Weighted ensemble
    weighted_sum = np.zeros((h, w), dtype=np.float64)
    weight_total = 0.0
    for tid, output in results.items():
        wt = weights[tid]
        weighted_sum += wt * output.astype(np.float64)
        weight_total += wt
    if weight_total > 0:
        weighted_map = weighted_sum / weight_total
    else:
        weighted_map = np.zeros((h, w), dtype=np.float64)

    # Consensus map
    consensus = np.zeros((h, w), dtype=np.int32)
    for output in results.values():
        consensus += (output > 0.5).astype(np.int32)
    consensus_threshold = max(1, len(techniques) // 4)
    consensus_mask = (consensus >= consensus_threshold).astype(np.float64)

    # Final: max of weighted ensemble and consensus mask
    final = np.maximum(weighted_map, consensus_mask)
    final_uint8 = np.clip(final * 255, 0, 255).astype(np.uint8)

    # Upscale back to original dimensions if we downsampled
    if scale < 1.0:
        final_uint8 = cv2.resize(final_uint8, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
        if mode == "test":
            # Also upscale per-technique results for diagnostics
            for tid in results:
                results[tid] = cv2.resize(results[tid], (orig_w, orig_h),
                                          interpolation=cv2.INTER_LINEAR)

    elapsed_ms = (time.time() - start) * 1000

    result = {
        "border_map": final_uint8,
        "techniques_run": len(results),
        "processing_ms": round(elapsed_ms, 1),
        "consensus_count": int(consensus.max()),
    }

    if mode == "test":
        result["per_technique"] = results

    return result


def _run_one(tid, fn, preprocessed):
    """Run a single technique safely."""
    output = fn(preprocessed)
    if output.dtype == np.uint8:
        output = output.astype(np.float32) / 255.0
    return np.clip(output, 0.0, 1.0).astype(np.float32)

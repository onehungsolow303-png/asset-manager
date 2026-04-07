"""Quality metric functions for image comparison.

Progressive quality gates (fast -> expensive):
1. File/format check       ~1ms
2. Perceptual hash (pHash) ~5ms
3. PSNR                    ~20ms
4. SSIM                    ~100ms
5. Alpha IoU               ~50ms
6. Alpha MAE               ~50ms
7. Region analysis          ~200ms
"""

import numpy as np
from PIL import Image

DEFAULT_THRESHOLDS = {
    # Baseline thresholds — set just below current values as regression detectors.
    # Current metrics (2026-03-29): dark pHash=26, PSNR=2.96, SSIM=0.097, aIoU=0.977, aMAE=4.71
    #                               light pHash=16, PSNR=3.43, SSIM=0.39, aIoU=0.997, aMAE=0.61
    # Tighten these as extraction quality improves.
    "phash_max_distance": 30,     # Dark=26, Light=16 — detect > 15% regression
    "psnr_min_db": 2.5,           # Dark=2.96, Light=3.43 — detect major degradation
    "ssim_min": 0.05,             # Dark=0.097, Light=0.39 — detect structural collapse
    "alpha_iou_min": 0.95,        # Dark=0.977, Light=0.997 — tight: alpha mask is critical
    "alpha_mae_max": 8.0,         # Dark=4.71, Light=0.61 — detect alpha precision loss
}


def alpha_stats(img: Image.Image) -> dict:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    alpha = np.array(img)[:, :, 3]
    total = alpha.size
    transparent = float(np.sum(alpha == 0)) / total * 100
    opaque = float(np.sum(alpha == 255)) / total * 100
    semi = 100.0 - transparent - opaque
    return {
        "transparent": round(transparent, 2),
        "semi": round(semi, 2),
        "opaque": round(opaque, 2),
    }


def alpha_iou(test_img: Image.Image, ref_img: Image.Image, threshold: int = 10) -> float:
    if test_img.size != ref_img.size:
        test_img = test_img.resize(ref_img.size, Image.LANCZOS)
    t_alpha = np.array(test_img.convert("RGBA"))[:, :, 3]
    r_alpha = np.array(ref_img.convert("RGBA"))[:, :, 3]
    t_trans = t_alpha < threshold
    r_trans = r_alpha < threshold
    intersection = float(np.sum(t_trans & r_trans))
    union = float(np.sum(t_trans | r_trans))
    if union == 0:
        return 1.0
    return round(intersection / union, 4)


def alpha_mae(test_img: Image.Image, ref_img: Image.Image) -> float:
    if test_img.size != ref_img.size:
        test_img = test_img.resize(ref_img.size, Image.LANCZOS)
    t_alpha = np.array(test_img.convert("RGBA"))[:, :, 3].astype(float)
    r_alpha = np.array(ref_img.convert("RGBA"))[:, :, 3].astype(float)
    return round(float(np.mean(np.abs(t_alpha - r_alpha))), 2)


def region_opaque_pct(img: Image.Image, x_start: float, x_end: float,
                      y_start: float, y_end: float) -> float:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]
    y0, y1 = int(h * y_start), int(h * y_end)
    x0, x1 = int(w * x_start), int(w * x_end)
    region = arr[y0:y1, x0:x1, 3]
    if region.size == 0:
        return 0.0
    return round(float(np.sum(region > 128)) / region.size * 100, 2)


def pixel_diff_count(img_a: Image.Image, img_b: Image.Image) -> int:
    a = np.array(img_a.convert("RGBA"))
    b = np.array(img_b.convert("RGBA"))
    if a.shape != b.shape:
        img_b_r = img_b.resize((img_a.width, img_a.height), Image.LANCZOS)
        b = np.array(img_b_r.convert("RGBA"))
    diff = np.any(a != b, axis=2)
    return int(np.sum(diff))


def compute_ssim(test_img: Image.Image, ref_img: Image.Image) -> float:
    from skimage.metrics import structural_similarity
    if test_img.size != ref_img.size:
        test_img = test_img.resize(ref_img.size, Image.LANCZOS)
    # Normalize transparent pixels: zero RGB where alpha=0 in both images.
    # Without this, hidden RGB values (white matte in reference, black in test)
    # dominate the score despite being visually identical (both fully transparent).
    t_arr = np.array(test_img.convert("RGBA"))
    r_arr = np.array(ref_img.convert("RGBA"))
    t_arr[t_arr[:, :, 3] == 0, :3] = 0
    r_arr[r_arr[:, :, 3] == 0, :3] = 0
    t_gray = np.array(Image.fromarray(t_arr).convert("L"))
    r_gray = np.array(Image.fromarray(r_arr).convert("L"))
    min_dim = min(t_gray.shape)
    win_size = min(7, min_dim if min_dim % 2 == 1 else min_dim - 1)
    if win_size < 3:
        win_size = 3
    return round(float(structural_similarity(r_gray, t_gray, win_size=win_size,
                                              data_range=255)), 4)


def compute_psnr(test_img: Image.Image, ref_img: Image.Image) -> float:
    from skimage.metrics import peak_signal_noise_ratio
    if test_img.size != ref_img.size:
        test_img = test_img.resize(ref_img.size, Image.LANCZOS)
    # Normalize transparent pixels before comparison (same fix as SSIM)
    t_arr = np.array(test_img.convert("RGBA"))
    r_arr = np.array(ref_img.convert("RGBA"))
    t_arr[t_arr[:, :, 3] == 0, :3] = 0
    r_arr[r_arr[:, :, 3] == 0, :3] = 0
    mse = np.mean((t_arr.astype(float) - r_arr.astype(float)) ** 2)
    if mse == 0:
        return float("inf")
    return round(float(peak_signal_noise_ratio(r_arr, t_arr, data_range=255)), 2)


def compute_phash_distance(test_img: Image.Image, ref_img: Image.Image,
                           hash_size: int = 8) -> int:
    import imagehash
    h1 = imagehash.phash(test_img.convert("RGB"), hash_size=hash_size)
    h2 = imagehash.phash(ref_img.convert("RGB"), hash_size=hash_size)
    return h1 - h2


def generate_diff_heatmap(test_img: Image.Image, ref_img: Image.Image) -> Image.Image:
    import cv2
    if test_img.size != ref_img.size:
        test_img = test_img.resize(ref_img.size, Image.LANCZOS)
    t_arr = np.array(test_img.convert("RGBA")).astype(float)
    r_arr = np.array(ref_img.convert("RGBA")).astype(float)
    diff = np.max(np.abs(t_arr - r_arr), axis=2).astype(np.uint8)
    amplified = np.clip(diff * 3, 0, 255).astype(np.uint8)
    heatmap_bgr = cv2.applyColorMap(amplified, cv2.COLORMAP_JET)
    heatmap_rgb = cv2.cvtColor(heatmap_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(heatmap_rgb)


def run_quality_gates(test_img: Image.Image, ref_img: Image.Image,
                      thresholds: dict | None = None) -> dict:
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    metrics = {}
    failures = []

    phash_dist = compute_phash_distance(test_img, ref_img)
    metrics["phash_distance"] = phash_dist
    if phash_dist > t["phash_max_distance"]:
        failures.append(("phash_distance", phash_dist, f"<= {t['phash_max_distance']}"))
        return {"passed": False, "failures": failures, "metrics": metrics,
                "failed_at": "phash_distance"}

    psnr = compute_psnr(test_img, ref_img)
    metrics["psnr_db"] = psnr
    if psnr < t["psnr_min_db"]:
        failures.append(("psnr_db", psnr, f">= {t['psnr_min_db']}"))
        return {"passed": False, "failures": failures, "metrics": metrics,
                "failed_at": "psnr_db"}

    ssim = compute_ssim(test_img, ref_img)
    metrics["ssim"] = ssim
    if ssim < t["ssim_min"]:
        failures.append(("ssim", ssim, f">= {t['ssim_min']}"))
        return {"passed": False, "failures": failures, "metrics": metrics,
                "failed_at": "ssim"}

    iou = alpha_iou(test_img, ref_img)
    metrics["alpha_iou"] = iou
    if iou < t["alpha_iou_min"]:
        failures.append(("alpha_iou", iou, f">= {t['alpha_iou_min']}"))
        return {"passed": False, "failures": failures, "metrics": metrics,
                "failed_at": "alpha_iou"}

    mae = alpha_mae(test_img, ref_img)
    metrics["alpha_mae"] = mae
    if mae > t["alpha_mae_max"]:
        failures.append(("alpha_mae", mae, f"<= {t['alpha_mae_max']}"))
        return {"passed": False, "failures": failures, "metrics": metrics,
                "failed_at": "alpha_mae"}

    metrics["alpha_stats"] = alpha_stats(test_img)
    metrics["ref_alpha_stats"] = alpha_stats(ref_img)

    return {"passed": True, "failures": [], "metrics": metrics, "failed_at": None}

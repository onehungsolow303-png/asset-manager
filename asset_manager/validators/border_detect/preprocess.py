"""Shared image preprocessing — convert once, reuse across all techniques."""
import cv2
import numpy as np

def preprocess(img_bgr):
    if img_bgr.ndim != 3 or img_bgr.shape[2] != 3:
        raise ValueError(f"Expected (H, W, 3) image, got {img_bgr.shape}")
    bgr = img_bgr
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    ycbcr = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    gray_f = gray.astype(np.float64)
    integral = cv2.integral(gray_f)
    integral_sq = cv2.integral(gray_f * gray_f)
    return {
        "bgr": bgr, "rgb": rgb, "gray": gray, "hsv": hsv,
        "lab": lab, "ycbcr": ycbcr,
        "integral": integral, "integral_sq": integral_sq,
        "height": bgr.shape[0], "width": bgr.shape[1],
    }

"""Morphological operation techniques (5)."""
import cv2
import numpy as np

def morph_gradient(preprocessed):
    gray = preprocessed["gray"]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)
    return (grad.astype(np.float32) / 255.0)

def morph_blackhat(preprocessed):
    gray = preprocessed["gray"]
    result = np.zeros_like(gray, dtype=np.float64)
    for size in [15, 35, 55]:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (size, size))
        bh = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
        result = np.maximum(result, bh.astype(np.float64))
    result = result / result.max() if result.max() > 0 else result
    return result.astype(np.float32)

def morph_close_gaps(preprocessed):
    gray = preprocessed["gray"]
    inv = 255 - gray
    result = np.zeros_like(inv, dtype=np.float64)
    for size in [3, 7, 15]:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (size, size))
        closed = cv2.morphologyEx(inv, cv2.MORPH_CLOSE, kernel)
        result = np.maximum(result, closed.astype(np.float64))
    result = result / result.max() if result.max() > 0 else result
    return result.astype(np.float32)

def morph_tophat(preprocessed):
    gray = preprocessed["gray"]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
    th = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
    return (th.astype(np.float32) / 255.0)

def morph_width_probe(preprocessed):
    gray = preprocessed["gray"]
    inv = 255 - gray
    h, w = gray.shape
    result = np.zeros((h, w), dtype=np.float64)
    for radius in [3, 7, 12, 20]:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius*2+1, radius*2+1))
        eroded = cv2.erode(inv, kernel)
        dilated = cv2.dilate(eroded, kernel)
        result = np.maximum(result, dilated.astype(np.float64))
    result = result / result.max() if result.max() > 0 else result
    return result.astype(np.float32)

TECHNIQUES = [
    ("morph_gradient", morph_gradient), ("morph_blackhat", morph_blackhat),
    ("morph_close_gaps", morph_close_gaps), ("morph_tophat", morph_tophat),
    ("morph_width_probe", morph_width_probe),
]

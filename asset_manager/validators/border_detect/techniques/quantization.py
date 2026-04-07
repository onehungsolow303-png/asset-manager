"""Color quantization & grouping techniques (3)."""
import cv2
import numpy as np
from skimage.segmentation import slic

def quant_median(preprocessed):
    rgb = preprocessed["rgb"]
    h, w = rgb.shape[:2]
    pixels = rgb.reshape(-1, 3).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, _ = cv2.kmeans(pixels, 8, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    labels = labels.reshape(h, w)
    result = np.zeros((h, w), dtype=np.float32)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        shifted = np.roll(np.roll(labels, dy, axis=0), dx, axis=1)
        result += (labels != shifted).astype(np.float32)
    result = np.clip(result, 0, 1)
    result[0, :] = 0; result[-1, :] = 0; result[:, 0] = 0; result[:, -1] = 0
    return result.astype(np.float32)

def quant_kmeans(preprocessed):
    rgb = preprocessed["rgb"]
    h, w = rgb.shape[:2]
    pixels = rgb.reshape(-1, 3).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(pixels, 3, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    labels = labels.reshape(h, w)
    brightness = centers.sum(axis=1)
    border_label = brightness.argmin()
    return (labels == border_label).astype(np.float32)

def quant_slic(preprocessed):
    rgb = preprocessed["rgb"]
    h, w = rgb.shape[:2]
    segments = slic(rgb, n_segments=200, compactness=10, start_label=0)
    result = np.zeros((h, w), dtype=np.float32)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        shifted = np.roll(np.roll(segments, dy, axis=0), dx, axis=1)
        result += (segments != shifted).astype(np.float32)
    result = np.clip(result, 0, 1)
    result[0, :] = 0; result[-1, :] = 0; result[:, 0] = 0; result[:, -1] = 0
    return result.astype(np.float32)

TECHNIQUES = [
    ("quant_median", quant_median), ("quant_kmeans", quant_kmeans), ("quant_slic", quant_slic),
]

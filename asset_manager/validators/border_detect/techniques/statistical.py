"""Statistical method techniques (4)."""
import cv2
import numpy as np
from skimage.filters.rank import entropy
from skimage.morphology import disk

def stat_variance(preprocessed):
    gray = preprocessed["gray"].astype(np.float64)
    win = 11
    mean = cv2.blur(gray, (win, win))
    sq_mean = cv2.blur(gray**2, (win, win))
    variance = np.maximum(sq_mean - mean**2, 0)
    result = variance / variance.max() if variance.max() > 0 else variance
    return result.astype(np.float32)

def stat_entropy(preprocessed):
    gray = preprocessed["gray"]
    ent = entropy(gray, disk(5))
    result = ent.astype(np.float64)
    result = result / result.max() if result.max() > 0 else result
    return result.astype(np.float32)

def stat_mahalanobis(preprocessed):
    rgb = preprocessed["rgb"].astype(np.float64)
    h, w = rgb.shape[:2]
    pixels = rgb.reshape(-1, 3).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(pixels, 3, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    labels = labels.flatten()
    distances = np.zeros(len(pixels), dtype=np.float64)
    for i in range(3):
        mask = labels == i
        if mask.sum() == 0: continue
        distances[mask] = np.sqrt(np.sum((pixels[mask].astype(np.float64) - centers[i])**2, axis=1))
    result = distances.reshape(h, w)
    result = result / result.max() if result.max() > 0 else result
    return result.astype(np.float32)

def stat_mean_diff(preprocessed):
    rgb = preprocessed["rgb"].astype(np.float64)
    win = 15
    result = np.zeros(rgb.shape[:2], dtype=np.float64)
    for ch in range(3):
        channel = rgb[:, :, ch]
        local_mean = cv2.blur(channel, (win, win))
        diff = np.abs(channel - local_mean)
        result = np.maximum(result, diff)
    result = result / result.max() if result.max() > 0 else result
    return result.astype(np.float32)

TECHNIQUES = [
    ("stat_variance", stat_variance), ("stat_entropy", stat_entropy),
    ("stat_mahalanobis", stat_mahalanobis), ("stat_mean_diff", stat_mean_diff),
]

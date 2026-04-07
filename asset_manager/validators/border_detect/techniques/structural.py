"""Structural analysis techniques (4)."""
import cv2
import numpy as np

def struct_contour(preprocessed):
    gray = preprocessed["gray"]
    h, w = gray.shape
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None or len(contours) == 0:
        return np.zeros((h, w), dtype=np.float32)
    hierarchy = hierarchy[0]
    result = np.zeros((h, w), dtype=np.float32)
    depths = np.zeros(len(contours), dtype=np.int32)
    for i in range(len(contours)):
        depth = 0; parent = hierarchy[i][3]
        while parent >= 0: depth += 1; parent = hierarchy[parent][3]
        depths[i] = depth
    max_depth = depths.max() if len(depths) > 0 else 1
    for i, contour in enumerate(contours):
        weight = depths[i] / max_depth if max_depth > 0 else 0
        cv2.drawContours(result, [contour], -1, float(weight), 2)
    return result.astype(np.float32)

def struct_ccl(preprocessed):
    gray = preprocessed["gray"]
    h, w = gray.shape
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary)
    result = np.zeros((h, w), dtype=np.float32)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        shifted = np.roll(np.roll(labels, dy, axis=0), dx, axis=1)
        result += (labels != shifted).astype(np.float32)
    result = np.clip(result, 0, 1)
    result[0, :] = 0; result[-1, :] = 0; result[:, 0] = 0; result[:, -1] = 0
    return result.astype(np.float32)

def struct_distance(preprocessed):
    gray = preprocessed["gray"]
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    lap = cv2.Laplacian(dist, cv2.CV_32F)
    ridge = np.abs(lap)
    ridge = ridge / ridge.max() if ridge.max() > 0 else ridge
    return ridge.astype(np.float32)

def struct_watershed(preprocessed):
    gray = preprocessed["gray"]
    bgr = preprocessed["bgr"]
    h, w = gray.shape
    grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    _, sure_fg = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    sure_fg = cv2.erode(sure_fg, None, iterations=2)
    sure_bg = cv2.dilate(sure_fg, None, iterations=3)
    unknown = cv2.subtract(sure_bg, sure_fg)
    _, markers = cv2.connectedComponents(sure_fg)
    markers = markers + 1
    markers[unknown == 255] = 0
    markers_ws = cv2.watershed(bgr.copy(), markers.copy())
    result = np.zeros((h, w), dtype=np.float32)
    result[markers_ws == -1] = 1.0
    result = cv2.dilate(result, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    return result.astype(np.float32)

TECHNIQUES = [
    ("struct_contour", struct_contour), ("struct_ccl", struct_ccl),
    ("struct_distance", struct_distance), ("struct_watershed", struct_watershed),
]

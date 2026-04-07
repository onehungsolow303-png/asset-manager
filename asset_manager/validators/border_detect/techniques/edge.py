"""Edge detection techniques (8)."""

import cv2
import numpy as np


def edge_sobel(preprocessed):
    gray = preprocessed["gray"]
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.sqrt(gx ** 2 + gy ** 2)
    mag = mag / mag.max() if mag.max() > 0 else mag
    return mag.astype(np.float32)


def edge_scharr(preprocessed):
    gray = preprocessed["gray"]
    gx = cv2.Scharr(gray, cv2.CV_64F, 1, 0)
    gy = cv2.Scharr(gray, cv2.CV_64F, 0, 1)
    mag = np.sqrt(gx ** 2 + gy ** 2)
    mag = mag / mag.max() if mag.max() > 0 else mag
    return mag.astype(np.float32)


def edge_prewitt(preprocessed):
    gray = preprocessed["gray"].astype(np.float64)
    kx = np.array([[-1, 0, 1], [-1, 0, 1], [-1, 0, 1]], dtype=np.float64)
    ky = np.array([[-1, -1, -1], [0, 0, 0], [1, 1, 1]], dtype=np.float64)
    gx = cv2.filter2D(gray, cv2.CV_64F, kx)
    gy = cv2.filter2D(gray, cv2.CV_64F, ky)
    mag = np.sqrt(gx ** 2 + gy ** 2)
    mag = mag / mag.max() if mag.max() > 0 else mag
    return mag.astype(np.float32)


def edge_roberts(preprocessed):
    gray = preprocessed["gray"].astype(np.float64)
    k1 = np.array([[1, 0], [0, -1]], dtype=np.float64)
    k2 = np.array([[0, 1], [-1, 0]], dtype=np.float64)
    g1 = cv2.filter2D(gray, cv2.CV_64F, k1)
    g2 = cv2.filter2D(gray, cv2.CV_64F, k2)
    mag = np.sqrt(g1 ** 2 + g2 ** 2)
    mag = mag / mag.max() if mag.max() > 0 else mag
    return mag.astype(np.float32)


def edge_log(preprocessed):
    gray = preprocessed["gray"]
    blurred = cv2.GaussianBlur(gray, (5, 5), 1.0)
    lap = cv2.Laplacian(blurred, cv2.CV_64F)
    mag = np.abs(lap)
    mag = mag / mag.max() if mag.max() > 0 else mag
    return mag.astype(np.float32)


def edge_dog(preprocessed):
    gray = preprocessed["gray"]
    g1 = cv2.GaussianBlur(gray, (0, 0), sigmaX=2.0).astype(np.float64)
    g2 = cv2.GaussianBlur(gray, (0, 0), sigmaX=8.0).astype(np.float64)
    dog = np.abs(g1 - g2)
    dog = dog / dog.max() if dog.max() > 0 else dog
    return dog.astype(np.float32)


def edge_canny(preprocessed):
    gray = preprocessed["gray"]
    median = np.median(gray)
    low = max(10, int(0.5 * median))
    high = max(30, int(1.5 * median))
    edges = cv2.Canny(gray, low, high)
    return (edges / 255.0).astype(np.float32)


def edge_phase(preprocessed):
    gray = preprocessed["gray"].astype(np.float64)
    h, w = gray.shape
    result = np.zeros((h, w), dtype=np.float64)
    for sigma in [1.0, 2.0, 4.0, 8.0]:
        blurred = cv2.GaussianBlur(gray, (0, 0), sigmaX=sigma)
        lap = cv2.Laplacian(blurred, cv2.CV_64F)
        result += np.abs(lap)
    result = result / result.max() if result.max() > 0 else result
    return result.astype(np.float32)


TECHNIQUES = [
    ("edge_sobel", edge_sobel), ("edge_scharr", edge_scharr),
    ("edge_prewitt", edge_prewitt), ("edge_roberts", edge_roberts),
    ("edge_log", edge_log), ("edge_dog", edge_dog),
    ("edge_canny", edge_canny), ("edge_phase", edge_phase),
]

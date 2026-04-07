"""Texture analysis techniques (4)."""
import cv2
import numpy as np
from skimage.feature import local_binary_pattern, graycomatrix, graycoprops

def tex_lbp(preprocessed):
    gray = preprocessed["gray"]
    lbp = local_binary_pattern(gray, P=8, R=1, method="uniform")
    lbp_f = lbp.astype(np.float32)
    mean = cv2.blur(lbp_f, (11, 11))
    sq_mean = cv2.blur(lbp_f**2, (11, 11))
    variance = np.maximum(sq_mean - mean**2, 0)
    result = variance / variance.max() if variance.max() > 0 else variance
    return result.astype(np.float32)

def tex_gabor(preprocessed):
    gray = preprocessed["gray"].astype(np.float64)
    h, w = gray.shape
    result = np.zeros((h, w), dtype=np.float64)
    for theta in [0, np.pi/4, np.pi/2, 3*np.pi/4]:
        for sigma in [2.0, 4.0, 8.0]:
            kernel = cv2.getGaborKernel((21, 21), sigma=sigma, theta=theta, lambd=sigma*2, gamma=0.5, psi=0)
            filtered = cv2.filter2D(gray, cv2.CV_64F, kernel)
            result = np.maximum(result, np.abs(filtered))
    result = result / result.max() if result.max() > 0 else result
    return result.astype(np.float32)

def tex_glcm(preprocessed):
    gray = preprocessed["gray"]
    h, w = gray.shape
    quantized = (gray // 32).astype(np.uint8)
    result = np.zeros((h, w), dtype=np.float32)
    win = 16; step = 16  # larger step for speed (was 4)
    for y in range(0, h - win, step):
        for x in range(0, w - win, step):
            patch = quantized[y:y+win, x:x+win]
            glcm = graycomatrix(patch, distances=[1], angles=[0], levels=8, symmetric=True, normed=True)
            contrast = graycoprops(glcm, "contrast")[0, 0]
            result[y:y+step, x:x+step] = contrast
    result = result / result.max() if result.max() > 0 else result
    return result.astype(np.float32)

def tex_laws(preprocessed):
    gray = preprocessed["gray"].astype(np.float64)
    L5 = np.array([1, 4, 6, 4, 1], dtype=np.float64)
    E5 = np.array([-1, -2, 0, 2, 1], dtype=np.float64)
    S5 = np.array([-1, 0, 2, 0, -1], dtype=np.float64)
    result = np.zeros_like(gray, dtype=np.float64)
    for k1 in [L5, E5, S5]:
        for k2 in [L5, E5, S5]:
            kernel = np.outer(k1, k2)
            filtered = cv2.filter2D(gray, cv2.CV_64F, kernel)
            energy = cv2.blur(np.abs(filtered), (15, 15))
            result = np.maximum(result, energy)
    result = result / result.max() if result.max() > 0 else result
    return result.astype(np.float32)

TECHNIQUES = [
    ("tex_lbp", tex_lbp), ("tex_gabor", tex_gabor),
    ("tex_glcm", tex_glcm), ("tex_laws", tex_laws),
]

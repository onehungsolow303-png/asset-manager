"""Gradient analysis techniques (3)."""
import cv2
import numpy as np
from skimage.feature import structure_tensor, structure_tensor_eigenvalues

def grad_structure(preprocessed):
    gray = preprocessed["gray"].astype(np.float64)
    A_elems = structure_tensor(gray, sigma=1.5)
    l1, l2 = structure_tensor_eigenvalues(A_elems)
    result = l1 / l1.max() if l1.max() > 0 else l1
    return result.astype(np.float32)

def grad_harris(preprocessed):
    gray = preprocessed["gray"].astype(np.float32)
    harris = cv2.cornerHarris(gray, blockSize=3, ksize=3, k=0.04)
    harris = cv2.dilate(harris, None)
    result = np.maximum(harris, 0)
    result = result / result.max() if result.max() > 0 else result
    return result.astype(np.float32)

def grad_hog(preprocessed):
    gray = preprocessed["gray"]
    h, w = gray.shape
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.sqrt(gx**2 + gy**2)
    cell_size = 8
    result = np.zeros((h, w), dtype=np.float64)
    for cy in range(0, h - cell_size, cell_size):
        for cx in range(0, w - cell_size, cell_size):
            energy = mag[cy:cy+cell_size, cx:cx+cell_size].mean()
            result[cy:cy+cell_size, cx:cx+cell_size] = energy
    result = result / result.max() if result.max() > 0 else result
    return result.astype(np.float32)

TECHNIQUES = [
    ("grad_structure", grad_structure), ("grad_harris", grad_harris), ("grad_hog", grad_hog),
]

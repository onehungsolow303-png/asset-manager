"""Adaptive thresholding & frequency domain techniques (4)."""
import cv2
import numpy as np
from skimage.filters import threshold_sauvola, threshold_niblack

def adapt_sauvola(preprocessed):
    gray = preprocessed["gray"]
    thresh = threshold_sauvola(gray, window_size=25, k=0.2)
    return (gray < thresh).astype(np.float32)

def adapt_niblack(preprocessed):
    gray = preprocessed["gray"]
    thresh = threshold_niblack(gray, window_size=25, k=0.8)
    return (gray < thresh).astype(np.float32)

def freq_fft_highpass(preprocessed):
    gray = preprocessed["gray"].astype(np.float64)
    h, w = gray.shape
    f = np.fft.fft2(gray)
    fshift = np.fft.fftshift(f)
    cy, cx = h // 2, w // 2
    radius = min(h, w) // 10
    mask = np.ones((h, w), dtype=np.float64)
    y, x = np.ogrid[:h, :w]
    dist = np.sqrt((y - cy)**2 + (x - cx)**2)
    mask[dist <= radius] = 0
    transition = np.clip((dist - radius) / (radius * 0.5), 0, 1)
    mask = np.maximum(mask, transition)
    filtered = fshift * mask
    result = np.abs(np.fft.ifft2(np.fft.ifftshift(filtered)))
    result = result / result.max() if result.max() > 0 else result
    return result.astype(np.float32)

def freq_wavelet(preprocessed):
    gray = preprocessed["gray"].astype(np.float64)
    h, w = gray.shape
    result = np.zeros((h, w), dtype=np.float64)
    current = gray
    try:
        import pywt
        for level in range(1, 4):
            coeffs = pywt.dwt2(current, "haar")
            cA, (cH, cV, cD) = coeffs
            detail = np.sqrt(cH**2 + cV**2 + cD**2)
            detail_up = cv2.resize(detail, (w, h), interpolation=cv2.INTER_LINEAR)
            result = np.maximum(result, detail_up)
            current = cA
    except ImportError:
        for sigma in [1.0, 2.0, 4.0]:
            blurred = cv2.GaussianBlur(gray, (0, 0), sigmaX=sigma)
            lap = np.abs(cv2.Laplacian(blurred, cv2.CV_64F))
            result = np.maximum(result, lap)
    result = result / result.max() if result.max() > 0 else result
    return result.astype(np.float32)

TECHNIQUES = [
    ("adapt_sauvola", adapt_sauvola), ("adapt_niblack", adapt_niblack),
    ("freq_fft_highpass", freq_fft_highpass), ("freq_wavelet", freq_wavelet),
]

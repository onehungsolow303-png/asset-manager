"""Color-space analysis techniques (5)."""
import cv2
import numpy as np

def color_hsv_dark(preprocessed):
    """HSV dark-border mask — low V, low S = dark brown/gray borders."""
    hsv = preprocessed["hsv"]
    v = hsv[:, :, 2].astype(np.float32)
    s = hsv[:, :, 1].astype(np.float32)
    dark_score = np.clip(1.0 - v / 80.0, 0, 1)
    achromatic_score = np.clip(1.0 - s / 60.0, 0, 1)
    return (dark_score * achromatic_score).astype(np.float32)

def color_lab_delta(preprocessed):
    """CIELAB Delta-E transition map."""
    lab = preprocessed["lab"].astype(np.float64)
    h, w = lab.shape[:2]
    delta = np.zeros((h, w), dtype=np.float64)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        shifted = np.roll(np.roll(lab, dy, axis=0), dx, axis=1)
        diff = np.sqrt(np.sum((lab - shifted) ** 2, axis=2))
        delta = np.maximum(delta, diff)
    delta[0, :] = 0; delta[-1, :] = 0; delta[:, 0] = 0; delta[:, -1] = 0
    delta = delta / delta.max() if delta.max() > 0 else delta
    return delta.astype(np.float32)

def color_ycbcr_luma(preprocessed):
    """YCbCr luminance edges — Sobel on Y channel."""
    y_ch = preprocessed["ycbcr"][:, :, 0]
    gx = cv2.Sobel(y_ch, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(y_ch, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.sqrt(gx**2 + gy**2)
    mag = mag / mag.max() if mag.max() > 0 else mag
    return mag.astype(np.float32)

def color_rgb_gradient(preprocessed):
    """RGB Euclidean gradient — max color distance to 4-neighbors."""
    rgb = preprocessed["rgb"].astype(np.float64)
    h, w = rgb.shape[:2]
    max_dsq = np.zeros((h, w), dtype=np.float64)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        shifted = np.roll(np.roll(rgb, dy, axis=0), dx, axis=1)
        dsq = np.sum((rgb - shifted)**2, axis=2)
        max_dsq = np.maximum(max_dsq, dsq)
    max_dsq[0, :] = 0; max_dsq[-1, :] = 0; max_dsq[:, 0] = 0; max_dsq[:, -1] = 0
    result = np.sqrt(max_dsq)
    result = result / result.max() if result.max() > 0 else result
    return result.astype(np.float32)

def color_achromatic(preprocessed):
    """Dark achromatic filter — near-black low-chroma pixels."""
    rgb = preprocessed["rgb"].astype(np.float32)
    r, g, b = rgb[:,:,0], rgb[:,:,1], rgb[:,:,2]
    max_ch = np.maximum(np.maximum(r, g), b)
    min_ch = np.minimum(np.minimum(r, g), b)
    spread = max_ch - min_ch
    dark_score = np.clip(1.0 - max_ch / 55.0, 0, 1)
    achromatic_score = np.clip(1.0 - spread / 12.0, 0, 1)
    return (dark_score * achromatic_score).astype(np.float32)

TECHNIQUES = [
    ("color_hsv_dark", color_hsv_dark), ("color_lab_delta", color_lab_delta),
    ("color_ycbcr_luma", color_ycbcr_luma), ("color_rgb_gradient", color_rgb_gradient),
    ("color_achromatic", color_achromatic),
]

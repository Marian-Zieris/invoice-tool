import cv2
import numpy as np


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _deskew(gray: np.ndarray) -> np.ndarray:
    """Narovná mírně natočený scan/foto podle úhlu tmavých pixelů (textu)."""
    inverted = cv2.bitwise_not(gray)
    _, thresh = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(thresh > 0))
    if coords.shape[0] < 20:
        return gray

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) < 0.3 or abs(angle) > 20:
        # Malý úhel nestojí za rotaci, velký je spíš chybná detekce než skutečný náklon.
        return gray

    (h, w) = gray.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def _enhance_contrast(gray: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def preprocess_image(image: np.ndarray) -> np.ndarray:
    """Narovnání a zvýšení kontrastu obrázku faktury/účtenky před OCR.

    Vrací 3-kanálový BGR obrázek (kompatibilní s pytesseract i RapidOCR).
    """
    gray = _to_grayscale(image)
    deskewed = _deskew(gray)
    contrasted = _enhance_contrast(deskewed)
    return cv2.cvtColor(contrasted, cv2.COLOR_GRAY2BGR)

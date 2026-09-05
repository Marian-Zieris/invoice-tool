import logging
import os
from typing import List

import cv2
import numpy as np
from pdf2image import convert_from_path

from app.services.preprocess import preprocess_image

logger = logging.getLogger(__name__)

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None

try:
    from rapidocr_onnxruntime import RapidOCR

    _rapid_engine = RapidOCR()
except ImportError:  # pragma: no cover
    _rapid_engine = None

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
TESSERACT_LANGS = os.environ.get("TESSERACT_LANGS", "ces+eng")
PDF_DPI = int(os.environ.get("PDF_DPI", "300"))


def _load_pages(file_path: str) -> List[np.ndarray]:
    """Načte soubor jako seznam BGR obrázků (jedna položka na stránku)."""
    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".pdf":
        pil_pages = convert_from_path(file_path, dpi=PDF_DPI)
        if not pil_pages:
            raise ValueError(f"PDF has no renderable pages: {file_path}")
        return [cv2.cvtColor(np.array(page.convert("RGB")), cv2.COLOR_RGB2BGR) for page in pil_pages]

    if extension in SUPPORTED_IMAGE_EXTENSIONS:
        image = cv2.imread(file_path)
        if image is None:
            raise ValueError(f"Unable to read image file: {file_path}")
        return [image]

    raise ValueError(f"Unsupported file type for OCR: {extension or 'unknown'}")


def _ocr_page_with_rapidocr(image: np.ndarray) -> str:
    if _rapid_engine is None:
        raise RuntimeError("rapidocr_onnxruntime is not installed.")
    result, _ = _rapid_engine(image)
    if not result:
        return ""
    return "\n".join(item[1] for item in result).strip()


def _ocr_page_with_tesseract(image: np.ndarray) -> str:
    if pytesseract is None:
        raise RuntimeError("pytesseract is not installed.")
    return pytesseract.image_to_string(image, lang=TESSERACT_LANGS, config="--psm 6").strip()


def _ocr_page(image: np.ndarray) -> str:
    """Nejlepší dostupný OCR engine na jednu stránku: RapidOCR primárně, Tesseract jako fallback."""
    processed = preprocess_image(image)

    try:
        text = _ocr_page_with_rapidocr(processed)
        if text:
            return text
    except Exception:
        logger.warning("RapidOCR failed on page, falling back to Tesseract.", exc_info=True)

    try:
        return _ocr_page_with_tesseract(processed)
    except Exception:
        logger.warning("Tesseract fallback also failed for page.", exc_info=True)
        return ""


def extract_text_from_file(file_path: str) -> str:
    """Vrátí spojený OCR text ze všech stránek souboru. Prázdný string = OCR selhalo."""
    pages = _load_pages(file_path)
    texts = [_ocr_page(page) for page in pages]
    return "\n\n".join(text for text in texts if text).strip()

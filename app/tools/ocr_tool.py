"""
Vision / OCR tool — REAL, not a stub.

Reads text out of a scanned image using Tesseract, exactly as the
"Vision + OCR" box in the architecture reads scanned inspection reports
and P&ID drawings.

Requires the Tesseract OS binary as well as pytesseract — see
docs/SETUP.md step 4.

Owner: Track B.
"""
import pytesseract
from PIL import Image
from .. import config

if config.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD


def ocr_image(image_path: str) -> str:
    """Extract text from an image file. Raises a clear error if the
    Tesseract binary is missing, since that is the most common setup
    mistake for new teammates."""
    try:
        img = Image.open(image_path)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Could not open image {image_path}: {e}") from e

    try:
        text = pytesseract.image_to_string(img)
    except pytesseract.TesseractNotFoundError as e:
        raise RuntimeError(
            "Tesseract binary not found. Install it:\n"
            "  Mac:     brew install tesseract\n"
            "  Linux:   sudo apt install tesseract-ocr\n"
            "  Windows: install the UB-Mannheim build and add it to PATH"
        ) from e

    # If simple OCR yielded little to no text, try image preprocessing
    if len(text.strip()) < 15:
        # Pass 1: Try cv2 grayscale + Otsu thresholding / adaptive thresholding
        try:
            import cv2
            import numpy as np
            cv_img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if cv_img is not None:
                # Upscale if low resolution
                h, w = cv_img.shape[:2]
                if w < 1000 or h < 1000:
                    cv_img = cv2.resize(cv_img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
                
                # Otsu binarization
                _, thresh = cv2.threshold(cv_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                t_otsu = pytesseract.image_to_string(thresh, config="--psm 6").strip()
                if len(t_otsu) > len(text):
                    text = t_otsu
                
                # Sparse text mode for engineering schematics
                if len(text.strip()) < 15:
                    t_sparse = pytesseract.image_to_string(cv_img, config="--psm 11").strip()
                    if len(t_sparse) > len(text):
                        text = t_sparse
        except Exception:
            pass

        # Pass 2: PIL contrast enhancement fallback
        if len(text.strip()) < 15:
            try:
                from PIL import ImageEnhance, ImageFilter
                enhanced = img.convert("L")
                enhanced = ImageEnhance.Contrast(enhanced).enhance(2.0)
                t_pil = pytesseract.image_to_string(enhanced).strip()
                if len(t_pil) > len(text):
                    text = t_pil
            except Exception:
                pass

    return text.strip()

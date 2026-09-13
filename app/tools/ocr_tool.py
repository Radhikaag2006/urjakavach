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

    return text.strip()

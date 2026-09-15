"""
Unified document content extractor.
Extracts text cleanly from images, PDFs, Word docs, code files, and plain text.
"""
import os
import re
from .ocr_tool import ocr_image

def extract_text_from_pdf(path: str) -> str:
    """Extract plain text from a PDF file using available libraries or stream parsing."""
    # 1. Try pypdf / pypdf2
    for mod_name in ("pypdf", "pypdf2"):
        try:
            mod = __import__(mod_name)
            reader = mod.PdfReader(path)
            parts = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
            full_text = "\n\n".join(parts).strip()
            if len(full_text) > 10:
                return full_text
        except Exception:
            pass

    # 2. Try pymupdf / fitz
    try:
        import fitz
        doc = fitz.open(path)
        parts = [page.get_text() for page in doc]
        full_text = "\n\n".join(parts).strip()
        if len(full_text) > 10:
            return full_text
    except Exception:
        pass

    # 3. Fallback: Parse visible text fragments and stream strings
    try:
        with open(path, "rb") as f:
            content = f.read()
        # Find ASCII/printable text sequences longer than 4 chars
        printable = re.findall(b"[A-Za-z0-9 .,:;!?()'\"]{5,}", content)
        text_candidates = [p.decode("latin-1", errors="ignore") for p in printable]
        # Filter out PDF metadata keywords
        filtered = [
            s for s in text_candidates
            if not any(k in s for k in ("Font", "Type", "Filter", "FlateDecode", "Catalog", "Length", "Stream", "obj", "endobj"))
        ]
        fallback_text = "\n".join(filtered[:50]).strip()
        if fallback_text:
            return fallback_text
    except Exception:
        pass

    return ""

def extract_file_content(path: str, filename: str = "", mime_type: str = "", content_type: str = "", **kwargs) -> str:
    """Extract readable text from any supported file type."""
    mime = (mime_type or content_type or "").lower()
    base_name = os.path.basename(path).lower()
    custom_name = (filename or "").lower()
    
    # Images -> OCR (Tesseract)
    is_img = (mime.startswith("image/")) or any(
        base_name.endswith(ext) or custom_name.endswith(ext) or (f"{ext} " in custom_name) or (f"{ext}(" in custom_name)
        for ext in [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"]
    )
    if is_img:
        return ocr_image(path)
        
    # PDF documents
    is_pdf = (mime == "application/pdf") or base_name.endswith(".pdf") or custom_name.endswith(".pdf") or (".pdf " in custom_name)
    if is_pdf:
        text = extract_text_from_pdf(path)
        if text:
            return text
        try:
            return ocr_image(path)
        except Exception:
            return ""

    # Microsoft Word .docx
    if base_name.endswith(".docx") or custom_name.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(path)
            paras = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paras).strip()
        except Exception:
            pass

    # Check for binary files to prevent dumping bytecode into text
    try:
        with open(path, "rb") as f:
            header = f.read(512)
        if b"\x00" in header:
            # Binary file not matched above; attempt OCR as last resort
            try:
                ocr_res = ocr_image(path)
                if ocr_res.strip():
                    return ocr_res
            except Exception:
                pass
            return ""
    except Exception:
        pass

    # Plain text, code, markdown, csv, json, logs
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(15000).strip()
    except Exception:
        try:
            with open(path, "r", encoding="latin-1", errors="ignore") as f:
                return f.read(15000).strip()
        except Exception:
            return ""

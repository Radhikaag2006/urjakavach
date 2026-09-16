"""
Unified document content extractor.
Extracts text cleanly from images, PDFs, Word docs, code files, and plain text.
"""
import os
import re
from .ocr_tool import ocr_image

def extract_text_from_pdf(path: str) -> str:
    """Extract plain text from a PDF file using pypdf, with OCR fallback on embedded images."""
    extracted_pages = []

    # 1. Primary engine: pypdf
    try:
        import pypdf
        reader = pypdf.PdfReader(path)
        for page_idx, page in enumerate(reader.pages):
            # Extract digital text
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                extracted_pages.append(text)
            else:
                # If page has no selectable text (scanned PDF), extract images and OCR them
                for img_obj in getattr(page, "images", []):
                    try:
                        import io
                        from PIL import Image
                        import pytesseract
                        pil_img = Image.open(io.BytesIO(img_obj.data))
                        ocr_txt = pytesseract.image_to_string(pil_img).strip()
                        if ocr_txt:
                            extracted_pages.append(ocr_txt)
                    except Exception:
                        pass
        
        full_text = "\n\n".join(extracted_pages).strip()
        if full_text:
            # Normalize Google Docs / Skia PDF artifacts where words are separated by '\n \n'
            cleaned = re.sub(r"\n[ \t]*\n", " ", full_text)
            cleaned = re.sub(r"\s+([0-9]+\.\s+[A-Z])", r"\n\n\1", cleaned)
            cleaned = re.sub(r"\s+(EXPERIMENT\s+[0-9]+)", r"\n\n\1", cleaned)
            cleaned = re.sub(r"\s+(●|•)\s*", r"\n• ", cleaned)
            return cleaned.strip()
    except Exception:
        pass

    # 2. Secondary engine: fitz (PyMuPDF) if installed
    try:
        import fitz
        doc = fitz.open(path)
        parts = [page.get_text().strip() for page in doc if page.get_text().strip()]
        if parts:
            return "\n\n".join(parts).strip()
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

    # Spreadsheets and tabular data (.csv, .tsv, .xlsx, .xls)
    if any(base_name.endswith(ext) or custom_name.endswith(ext) for ext in [".csv", ".tsv"]):
        try:
            import csv
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                delimiter = "\t" if (base_name.endswith(".tsv") or custom_name.endswith(".tsv")) else ","
                reader = csv.reader(f, delimiter=delimiter)
                rows = [row for row in reader if any(cell.strip() for cell in row)]
            if rows:
                headers = rows[0]
                sample_rows = rows[1:25]
                table_lines = [f"[TABULAR DATASET: {custom_name or base_name} - {len(rows)} total rows, {len(headers)} columns]"]
                table_lines.append("| " + " | ".join(headers) + " |")
                table_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                for r in sample_rows:
                    # Pad or truncate row to header length
                    padded = (r + [""] * len(headers))[:len(headers)]
                    table_lines.append("| " + " | ".join(padded) + " |")
                if len(rows) > 25:
                    table_lines.append(f"... [{len(rows) - 25} more rows omitted for brevity]")
                return "\n".join(table_lines)
        except Exception:
            pass

    # Microsoft Excel (.xlsx)
    if any(base_name.endswith(ext) or custom_name.endswith(ext) for ext in [".xlsx", ".xls"]):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
            sheet_names = wb.sheetnames
            extracted_sheets = []
            for sname in sheet_names[:3]:
                sheet = wb[sname]
                rows = []
                for row in sheet.iter_rows(values_only=True):
                    if any(cell is not None for cell in row):
                        rows.append([str(c) if c is not None else "" for c in row])
                    if len(rows) >= 30:
                        break
                if rows:
                    extracted_sheets.append(f"Sheet: {sname}\n" + "\n".join("\t".join(r) for r in rows))
            if extracted_sheets:
                return f"[EXCEL SPREADSHEET: {custom_name or base_name}]\n" + "\n\n".join(extracted_sheets)
        except Exception:
            pass

    # Source code identification
    code_extensions = {
        ".py": "Python", ".cpp": "C++", ".c": "C", ".h": "C/C++ Header",
        ".hpp": "C++ Header", ".java": "Java", ".js": "JavaScript",
        ".ts": "TypeScript", ".html": "HTML", ".css": "CSS",
        ".json": "JSON", ".yaml": "YAML", ".yml": "YAML",
        ".xml": "XML", ".toml": "TOML", ".sql": "SQL",
        ".sh": "Shell Script", ".bash": "Bash", ".zsh": "Zsh",
        ".rs": "Rust", ".go": "Go", ".kt": "Kotlin",
        ".swift": "Swift", ".rb": "Ruby", ".php": "PHP",
    }
    for ext, lang in code_extensions.items():
        if base_name.endswith(ext) or custom_name.endswith(ext):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(20000).strip()
                return f"[SOURCE CODE FILE: {custom_name or base_name} ({lang})]\n{content}"
            except Exception:
                pass

    # Check for binary files to prevent dumping bytecode into text
    try:
        with open(path, "rb") as f:
            header = f.read(512)
        if b"\x00" in header:
            # Binary file not matched above; attempt OCR as last resort (e.g. extension-less image)
            try:
                ocr_res = ocr_image(path)
                if ocr_res.strip():
                    return ocr_res
            except Exception:
                pass
            return f"[BINARY FILE: {custom_name or base_name} ({len(header)} bytes examined)]"
    except Exception:
        pass

    # Plain text, markdown, configuration, logs, or any other readable text
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(20000).strip()
    except Exception:
        try:
            with open(path, "r", encoding="latin-1", errors="ignore") as f:
                return f.read(20000).strip()
        except Exception:
            return ""

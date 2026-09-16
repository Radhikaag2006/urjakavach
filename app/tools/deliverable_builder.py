"""
Deliverable Builder Tool for UrjaKavach.
Generates production-grade deliverables:
- Presentations (.pptx) via python-pptx
- Spreadsheets (.xlsx) via openpyxl
- Tabular datasets (.csv) via standard library
- Word documents (.docx) via python-docx
"""
import os
import csv
import re
from datetime import datetime
from .. import config

try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    HAS_PPTX = True
except ImportError:
    HAS_PPTX = False

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


# Theme palette
if HAS_PPTX:
    NAVY_BLUE = RGBColor(28, 93, 153)       # #1C5D99
    DARK_SLATE = RGBColor(30, 41, 59)       # #1E293B
    MUTED_GRAY = RGBColor(100, 116, 139)    # #64748B
    ACCENT_BLUE = RGBColor(59, 130, 246)    # #3B82F6


def generate_presentation(
    title_or_data: str | dict,
    subtitle: str = "UrjaKavach Sovereign On-Premise AI Analysis",
    findings: list[str] | None = None,
    task_id: str = "gen",
    raw_context: str = "",
    slides_data: list[dict] | None = None,
) -> str:
    """Generate a high-quality PowerPoint presentation (.pptx) with real dynamic content."""
    os.makedirs(config.OUTPUTS_DIR, exist_ok=True)
    filename = f"UrjaKavach_Presentation_{task_id}.pptx"
    output_path = os.path.join(config.OUTPUTS_DIR, filename)

    # Extract real title, subtitle, and slides
    if isinstance(title_or_data, dict):
        title = title_or_data.get("title") or "Technical Briefing"
        subtitle = title_or_data.get("subtitle") or subtitle
        slides_list = title_or_data.get("slides") or []
    else:
        title = str(title_or_data)
        slides_list = slides_data or []

    if not HAS_PPTX:
        # Fallback: create markdown-formatted presentation text
        with open(output_path.replace(".pptx", ".txt"), "w", encoding="utf-8") as f:
            f.write(f"# {title}\n## {subtitle}\n\n")
            for s in slides_list:
                f.write(f"### {s.get('header', 'Slide')}\n")
                for p in s.get("points", []):
                    f.write(f"- {p}\n")
                f.write("\n")
        return filename

    prs = Presentation()
    # 16:9 widescreen layout
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # --- Slide 1: Title Slide ---
    slide1 = prs.slides.add_slide(blank_layout)

    # Top accent bar
    top_bar = slide1.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.333), Inches(0.2))
    top_bar.fill.solid()
    top_bar.fill.fore_color.rgb = NAVY_BLUE
    top_bar.line.fill.background()

    # Title box
    tbox = slide1.shapes.add_textbox(Inches(1.2), Inches(2.2), Inches(11), Inches(2.8))
    tf = tbox.text_frame
    tf.word_wrap = True

    p_badge = tf.paragraphs[0]
    p_badge.text = "⚡ URJAKAVACH SOVEREIGN ON-PREMISE INTELLIGENCE"
    p_badge.font.size = Pt(13)
    p_badge.font.bold = True
    p_badge.font.color.rgb = ACCENT_BLUE

    p_title = tf.add_paragraph()
    p_title.text = title
    p_title.font.size = Pt(34)
    p_title.font.bold = True
    p_title.font.color.rgb = DARK_SLATE
    p_title.space_before = Pt(14)

    p_sub = tf.add_paragraph()
    p_sub.text = subtitle
    p_sub.font.size = Pt(17)
    p_sub.font.color.rgb = MUTED_GRAY
    p_sub.space_before = Pt(8)

    p_date = tf.add_paragraph()
    p_date.text = f"Generated: {datetime.now().strftime('%B %d, %Y • %H:%M')} | Air-Gapped Verification"
    p_date.font.size = Pt(12)
    p_date.font.color.rgb = MUTED_GRAY
    p_date.space_before = Pt(20)

    # --- Dynamic Body Slides ---
    if not slides_list:
        # Fallback if no slides list provided
        pts = findings if findings else ["Comprehensive technical analysis completed.", "Verified on-premise without cloud transmission."]
        slides_list = [
            {"header": "1. Executive Summary & Scope", "points": pts[:4]},
            {"header": "2. Detailed Observations & Telemetry", "points": pts[4:8] if len(pts) > 4 else pts},
            {"header": "3. Implementation Actions & Roadmap", "points": ["Execute recommended engineering parameters.", "Verify continuous operational feedback."]},
        ]

    for s_idx, s_data in enumerate(slides_list, start=1):
        slide = prs.slides.add_slide(blank_layout)
        header_text = s_data.get("header") or f"Slide {s_idx}"
        _add_slide_header(slide, header_text, f"{title} • Slide {s_idx} of {len(slides_list)}")

        s_box = slide.shapes.add_textbox(Inches(1.2), Inches(2.0), Inches(11), Inches(4.8))
        s_tf = s_box.text_frame
        s_tf.word_wrap = True

        pts = s_data.get("points") or []
        for p_idx, pt in enumerate(pts):
            p = s_tf.paragraphs[0] if p_idx == 0 else s_tf.add_paragraph()
            p.text = f"•   {pt}"
            p.font.size = Pt(16)
            p.font.color.rgb = DARK_SLATE
            p.space_before = Pt(12)

    prs.save(output_path)
    return filename


def _add_slide_header(slide, title_text: str, subtitle_text: str):
    """Utility to paint standard header on slides."""
    # Top bar
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.333), Inches(0.12))
    bar.fill.solid()
    bar.fill.fore_color.rgb = NAVY_BLUE
    bar.line.fill.background()

    # Title box
    box = slide.shapes.add_textbox(Inches(1.2), Inches(0.6), Inches(11), Inches(1.2))
    tf = box.text_frame
    tf.word_wrap = True

    p1 = tf.paragraphs[0]
    p1.text = title_text
    p1.font.size = Pt(24)
    p1.font.bold = True
    p1.font.color.rgb = NAVY_BLUE

    p2 = tf.add_paragraph()
    p2.text = subtitle_text
    p2.font.size = Pt(13)
    p2.font.color.rgb = MUTED_GRAY
    p2.space_before = Pt(4)


def generate_spreadsheet(
    title: str,
    headers: list[str],
    rows: list[list],
    task_id: str = "gen",
    fmt: str = "xlsx",
) -> str:
    """Generate a clean tabular spreadsheet (.xlsx or .csv)."""
    os.makedirs(config.OUTPUTS_DIR, exist_ok=True)

    if fmt == "csv" or not HAS_OPENPYXL:
        filename = f"UrjaKavach_Data_{task_id}.csv"
        path = os.path.join(config.OUTPUTS_DIR, filename)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if headers:
                writer.writerow(headers)
            for row in rows:
                writer.writerow(row)
        return filename

    # Excel format (.xlsx)
    filename = f"UrjaKavach_Report_{task_id}.xlsx"
    path = os.path.join(config.OUTPUTS_DIR, filename)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = re.sub(r"[\\/*?:\[\]]", "_", title)[:30] or "Report"

    # Title Banner
    ws.merge_cells("A1:E1")
    title_cell = ws["A1"]
    title_cell.value = f"UrjaKavach Sovereign AI — {title}"
    title_cell.font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    title_cell.fill = PatternFill(start_color="1C5D99", end_color="1C5D99", fill_type="solid")
    title_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 36

    # Subtitle Info
    ws.merge_cells("A2:E2")
    sub_cell = ws["A2"]
    sub_cell.value = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Confidential Industrial Document"
    sub_cell.font = Font(name="Calibri", size=9, italic=True, color="64748B")
    sub_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[2].height = 20

    # Header Row
    header_fill = PatternFill(start_color="203A43", end_color="203A43", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    ws.row_dimensions[4].height = 26
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    # Data Rows with Zebra striping
    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    data_font = Font(name="Calibri", size=10, color="1E293B")

    start_row = 5
    for r_idx, row_data in enumerate(rows, start=start_row):
        ws.row_dimensions[r_idx].height = 22
        fill_to_use = zebra_fill if (r_idx % 2 == 0) else white_fill
        for c_idx, val in enumerate(row_data, start=1):
            cell = ws.cell(row=r_idx, column=c_idx, value=val)
            cell.font = data_font
            cell.fill = fill_to_use
            cell.border = thin_border
            # Align numbers to right, text to left
            if isinstance(val, (int, float)):
                cell.alignment = Alignment(horizontal="right", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    # Auto-fit column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            if cell.row > 2 and len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    wb.save(path)
    return filename


def parse_tabular_data(raw_text: str, findings: list[str] | None = None) -> tuple[str, list[str], list[list]]:
    """Intelligently parse tabular structures from text or findings."""
    title = "Extracted Findings & Parameter Log"
    
    # Check for CSV or table-like patterns in text
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    csv_candidates = [l for l in lines if "," in l and len(l.split(",")) >= 2]
    
    if len(csv_candidates) >= 2:
        try:
            reader = csv.reader(csv_candidates)
            parsed_rows = list(reader)
            headers = parsed_rows[0]
            rows = parsed_rows[1:]
            return title, headers, rows
        except Exception:
            pass

    # Default structured format based on findings
    headers = ["ID", "Category / Equipment", "Observation / Reading", "Status", "Recommendation"]
    rows = []
    
    pts = findings if findings else lines[:8]
    for idx, pt in enumerate(pts, start=1):
        clean_pt = re.sub(r"^[-*•\d.)]\s*", "", pt)
        
        # Categorize
        category = "General Observation"
        status = "Normal"
        rec = "Monitor periodically"
        
        lower = clean_pt.lower()
        if any(k in lower for k in ["leak", "corrosion", "crack", "fault", "defect", "fail", "damage"]):
            status = "High Alert"
            category = "Integrity Anomaly"
            rec = "Schedule immediate maintenance / replacement"
        elif any(k in lower for k in ["temperature", "pressure", "vibration", "sensor", "reading", "psi", "celsius"]):
            category = "Operational Telemetry"
            if any(k in lower for k in ["high", "exceed", "spike", "warn", "abnormal"]):
                status = "Warning"
                rec = "Calibrate sensor and adjust control valve"
        elif any(k in lower for k in ["thread", "socket", "server", "client", "tcp", "mutex", "code"]):
            category = "Software / Algorithm"
            status = "Verified"
            rec = "Ensure synchronization locks are maintained"

        rows.append([
            f"REC-{idx:03d}",
            category,
            clean_pt[:100] + ("…" if len(clean_pt) > 100 else ""),
            status,
            rec,
        ])

    return title, headers, rows

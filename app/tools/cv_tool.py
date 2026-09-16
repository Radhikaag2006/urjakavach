"""Industrial Computer Vision & Inspection Analyzer for UrjaKavach.

Provides sovereign, 100% on-premise CV analysis using OpenCV and NumPy:
1. Domain Classification & Sanity Validation:
   - Distinguishes genuine industrial drawings/P&IDs and plant equipment photos
     from non-engineering/organic imagery (e.g. flowers, foliage, faces, animals)
     to prevent false positive defect classifications.
2. Mechanical Drawing / P&ID Analysis:
   - Line segmentation & orthogonal CAD line network detection
   - Instrument tag & component symbol localization (ISA-5.1)
   - Equipment vessel contour bounding
3. Surface Defect & Corrosion Analysis:
   - Realistic iron oxide / rust HSV color thresholding & masking
   - Contour & pit anomaly detection on industrial metallic surfaces
   - Surface area affected (%) quantification & severity grading
4. Generates annotated inspection overlays saved to app/outputs/.
"""

import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from app import config


def analyze_engineering_image(
    image_path: str,
    analysis_type: str = "auto",
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Perform computer vision analysis on an engineering drawing or inspection photo.

    Includes domain sanity validation to reject non-engineering or organic imagery
    (such as flowers, nature photography, or pets) from being misclassified as
    blueprints or corroded metal.
    """
    if not task_id:
        task_id = str(uuid.uuid4())[:8]

    if not os.path.exists(image_path):
        return {
            "ok": False,
            "error": f"Image file not found: {image_path}",
            "task_id": task_id,
        }

    # Read image with OpenCV
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        try:
            pil_img = Image.open(image_path).convert("RGB")
            img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception as e:
            return {"ok": False, "error": f"Failed to load image: {e}", "task_id": task_id}

    h, w = img_bgr.shape[:2]
    annotated = img_bgr.copy()
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    # 1. Image Domain Analysis & Classification
    domain_info = _classify_image_domain(img_bgr, gray, hsv, analysis_type)
    domain = domain_info["domain"]

    # 2. Branch based on classified domain
    if domain == "non_engineering":
        results = _handle_non_engineering_image(annotated, domain_info, task_id)
        is_drawing = False
    elif domain == "mechanical_drawing":
        results = _analyze_mechanical_drawing(img_bgr, gray, annotated, task_id)
        is_drawing = True
    else:
        results = _analyze_inspection_photo(img_bgr, gray, annotated, task_id)
        is_drawing = False

    # Save annotated overlay image to outputs
    out_filename = f"cv_annotated_{task_id}.png"
    out_path = os.path.join(config.OUTPUTS_DIR, out_filename)
    cv2.imwrite(out_path, annotated)

    results.update({
        "ok": True,
        "task_id": task_id,
        "is_drawing": is_drawing,
        "domain": domain,
        "recognized_type": domain_info["recognized_type"],
        "confidence": domain_info["confidence"],
        "image_width": w,
        "image_height": h,
        "annotated_filename": out_filename,
        "annotated_url": f"/api/download/{out_filename}",
    })

    return results


def _classify_image_domain(
    img_bgr: np.ndarray,
    gray: np.ndarray,
    hsv: np.ndarray,
    analysis_type: str = "auto",
) -> Dict[str, Any]:
    """Inspects geometric, chromatic, and structural features to classify the image.

    Returns dict with domain ('mechanical_drawing' | 'surface_defect_inspection' | 'non_engineering').
    """
    h, w = gray.shape
    total_pixels = h * w

    # Calculate chromatic features
    mean_sat = float(np.mean(hsv[:, :, 1]))
    green_mask = cv2.inRange(hsv, (35, 40, 40), (85, 255, 255))
    green_ratio = float(np.sum(green_mask > 0)) / total_pixels

    # High-saturation color pixels (floral, natural pigments)
    vivid_color_mask = (hsv[:, :, 1] > 80) & (hsv[:, :, 2] > 60)
    vivid_ratio = float(np.sum(vivid_color_mask)) / total_pixels

    # White / light background ratio (typical for CAD paper & P&ID blueprints)
    white_ratio = float(np.sum(gray > 215)) / total_pixels

    # Edge analysis and line orthogonality
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=50, minLineLength=30, maxLineGap=10)
    ortho_ratio = 0.0
    line_count = 0

    if lines is not None:
        line_count = len(lines)
        angles = []
        for l in lines:
            pts = l[0] if getattr(l, "ndim", 1) > 1 else l
            dx = float(pts[2] - pts[0])
            dy = float(pts[3] - pts[1])
            ang = np.abs(np.arctan2(dy, dx) * 180.0 / np.pi)
            angles.append(ang)
        if angles:
            angles_arr = np.array(angles)
            # Orthogonal lines lie within 10 degrees of 0 (horizontal), 90 (vertical), or 180
            ortho = np.sum((angles_arr < 10) | (np.abs(angles_arr - 90) < 10) | (np.abs(angles_arr - 180) < 10))
            ortho_ratio = float(ortho) / len(angles_arr)

    # Classification Rules:
    # 1. Organic / Non-engineering (Botanical flowers, foliage, nature, non-industrial)
    is_botanical = (mean_sat > 70 and green_ratio > 0.10) or (vivid_ratio > 0.30 and ortho_ratio < 0.45)
    is_non_industrial = is_botanical or (mean_sat > 90 and ortho_ratio < 0.45 and white_ratio < 0.20)

    if is_non_industrial and analysis_type != "drawing":
        recognized = "organic_botanical_photo" if green_ratio > 0.10 else "natural_or_non_industrial_photo"
        return {
            "domain": "non_engineering",
            "recognized_type": recognized,
            "confidence": 0.95,
            "mean_sat": round(mean_sat, 1),
            "green_ratio": round(green_ratio, 3),
            "ortho_ratio": round(ortho_ratio, 2),
            "line_count": line_count,
        }

    # 2. Mechanical Drawing / P&ID
    # Engineering drawings have high orthogonality (piping headers, instrument leads) and low saturation
    is_drawing = False
    if analysis_type == "drawing":
        is_drawing = True
    elif (white_ratio > 0.35 and ortho_ratio > 0.55 and mean_sat < 50):
        is_drawing = True
    elif (line_count > 25 and ortho_ratio > 0.70 and mean_sat < 40):
        is_drawing = True
    elif white_ratio > 0.70 and mean_sat < 35:
        is_drawing = True

    if is_drawing:
        return {
            "domain": "mechanical_drawing",
            "recognized_type": "pid_or_cad_blueprint",
            "confidence": 0.92,
            "mean_sat": round(mean_sat, 1),
            "green_ratio": round(green_ratio, 3),
            "ortho_ratio": round(ortho_ratio, 2),
            "line_count": line_count,
        }

    # 3. Industrial Surface / Metallic Equipment Inspection
    return {
        "domain": "surface_defect_inspection",
        "recognized_type": "industrial_equipment_surface",
        "confidence": 0.88,
        "mean_sat": round(mean_sat, 1),
        "green_ratio": round(green_ratio, 3),
        "ortho_ratio": round(ortho_ratio, 2),
        "line_count": line_count,
    }


def _handle_non_engineering_image(
    annotated: np.ndarray,
    domain_info: Dict[str, Any],
    task_id: str,
) -> Dict[str, Any]:
    """Handles images identified as non-engineering (e.g. flowers, nature photos).

    Bypasses defect/corrosion detection to eliminate false positive alarms,
    and applies a clear notice banner.
    """
    h, w = annotated.shape[:2]

    # Draw semi-transparent header notice
    overlay = annotated.copy()
    banner_h = max(40, int(h * 0.12))
    cv2.rectangle(overlay, (0, 0), (w, banner_h), (30, 30, 30), -1)
    cv2.addWeighted(overlay, 0.75, annotated, 0.25, 0, annotated)

    # Border highlight indicating non-industrial input
    cv2.rectangle(annotated, (2, 2), (w - 2, h - 2), (0, 165, 255), 3)

    # Banner text
    title_text = "NON-ENGINEERING IMAGE DETECTED"
    desc_text = "Botanical/Natural photo recognized. CV defect & P&ID analysis skipped to prevent false alarms."
    cv2.putText(annotated, title_text, (15, int(banner_h * 0.45)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 165, 255), 2)
    cv2.putText(annotated, desc_text, (15, int(banner_h * 0.85)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (220, 220, 220), 1)

    summary_text = (
        "Non-Engineering Image Detected: The uploaded file is recognized as an organic/natural photograph "
        "(e.g., botanical flora or non-industrial scene). It is neither an engineering P&ID drawing nor an "
        "industrial equipment surface. Analysis was safely bypassed to prevent false defect alarms."
    )

    return {
        "analysis_mode": "non_engineering_rejected",
        "is_engineering_image": False,
        "corrosion_area_percentage": 0.0,
        "defect_count": 0,
        "severity": "Non-Applicable",
        "defects": [],
        "summary": summary_text,
        "warning": "For valid industrial analysis, please upload an engineering drawing (P&ID, CAD isometric) or a refinery equipment inspection photo.",
    }


def _analyze_mechanical_drawing(
    img_bgr: np.ndarray,
    gray: np.ndarray,
    annotated: np.ndarray,
    task_id: str,
) -> Dict[str, Any]:
    """Analyze mechanical drawings, P&IDs, or isometric blueprints."""
    h, w = gray.shape

    # 1. Edge & Line Detection (Piping runs)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=70, minLineLength=35, maxLineGap=10)
    line_count = len(lines) if lines is not None else 0

    if lines is not None:
        for line in lines[:60]:  # Highlight major piping lines
            pts = line[0] if getattr(line, "ndim", 1) > 1 else line
            x1, y1, x2, y2 = int(pts[0]), int(pts[1]), int(pts[2]), int(pts[3])
            cv2.line(annotated, (x1, y1), (x2, y2), (255, 100, 0), 2)

    # 2. Symbol & Tag Detection (Pumps, valves, circular tags)
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=25,
        param1=50,
        param2=35,
        minRadius=12,
        maxRadius=60,
    )
    detected_tags = []
    if circles is not None:
        circles = np.uint16(np.around(circles))
        for idx, i in enumerate(circles[0, :20]):
            cx, cy, r = int(i[0]), int(i[1]), int(i[2])
            cv2.circle(annotated, (cx, cy), r, (0, 255, 0), 2)
            cv2.circle(annotated, (cx, cy), 2, (0, 0, 255), 3)
            label = f"TAG-{idx+1}"
            cv2.putText(annotated, label, (cx - 15, cy - r - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 200, 0), 1)
            detected_tags.append({"x": cx, "y": cy, "radius": r, "label": label})

    # 3. Closed Component / Vessel Detection
    thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)[1]
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    components = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if 800 < area < (h * w * 0.4):
            x, y, cw, ch = cv2.boundingRect(cnt)
            if cw > 25 and ch > 25:
                cv2.rectangle(annotated, (x, y), (x + cw, y + ch), (0, 140, 255), 2)
                components.append({"x": x, "y": y, "w": cw, "h": ch, "area": int(area)})

    summary_text = (
        f"Mechanical Drawing Analysis: Identified {len(detected_tags)} instrument tag bubbles, "
        f"{line_count} piping line segments, and {len(components)} equipment bounding contours."
    )

    return {
        "analysis_mode": "mechanical_drawing",
        "is_engineering_image": True,
        "piping_line_segments": line_count,
        "instrument_tags_count": len(detected_tags),
        "equipment_components_count": len(components),
        "detected_tags": detected_tags[:15],
        "summary": summary_text,
    }


def _analyze_inspection_photo(
    img_bgr: np.ndarray,
    gray: np.ndarray,
    annotated: np.ndarray,
    task_id: str,
) -> Dict[str, Any]:
    """Analyze real inspection photos for corrosion, oxide scale, pits, and weld anomalies."""
    h, w = gray.shape
    total_pixels = h * w

    # 1. Color Segmentation for Rust/Corrosion in HSV
    # Restrict to authentic dark reddish-brown and orange iron-oxide scaling
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    lower_rust1 = np.array([8, 60, 30])
    upper_rust1 = np.array([24, 255, 200])

    rust_mask = cv2.inRange(hsv, lower_rust1, upper_rust1)

    # Morphological cleaning
    kernel = np.ones((5, 5), np.uint8)
    rust_mask = cv2.morphologyEx(rust_mask, cv2.MORPH_OPEN, kernel)
    rust_mask = cv2.morphologyEx(rust_mask, cv2.MORPH_DILATE, kernel)

    rust_pixels = int(np.sum(rust_mask > 0))
    corrosion_pct = round((rust_pixels / total_pixels) * 100.0, 2)

    # 2. Defect Contours & Bounding Boxes
    contours, _ = cv2.findContours(rust_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    defects = []
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for idx, cnt in enumerate(contours[:12]):
        area = cv2.contourArea(cnt)
        if area > 120:
            x, y, cw, ch = cv2.boundingRect(cnt)
            cv2.drawContours(annotated, [cnt], -1, (0, 0, 255), 2)
            cv2.rectangle(annotated, (x, y), (x + cw, y + ch), (0, 255, 255), 2)
            label = f"DEFECT #{idx+1} ({round(area, 0)}px)"
            cv2.putText(annotated, label, (x, max(15, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
            defects.append({
                "id": idx + 1,
                "x": x,
                "y": y,
                "w": cw,
                "h": ch,
                "area_px": int(area),
            })

    # Determine Severity
    if corrosion_pct > 25.0 or len(defects) >= 8:
        severity = "Critical"
    elif corrosion_pct > 10.0 or len(defects) >= 4:
        severity = "Major"
    elif corrosion_pct > 2.0 or len(defects) >= 1:
        severity = "Minor"
    else:
        severity = "Observation"

    summary_text = (
        f"Surface Inspection: Detected {len(defects)} defect/anomaly zones covering {corrosion_pct}% of surface area. "
        f"Overall Condition Severity: {severity}."
    )

    return {
        "analysis_mode": "surface_defect_inspection",
        "is_engineering_image": True,
        "corrosion_area_percentage": corrosion_pct,
        "defect_count": len(defects),
        "severity": severity,
        "defects": defects,
        "summary": summary_text,
    }

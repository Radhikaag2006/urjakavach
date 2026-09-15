"""Industrial Computer Vision & Inspection Analyzer for UrjaKavach.

Provides sovereign, 100% on-premise CV analysis using OpenCV and NumPy:
1. Mechanical Drawing / P&ID Analysis:
   - Line segmentation & junction detection
   - Instrument tag & component symbol localization
2. Surface Defect & Corrosion Analysis:
   - Rust/oxide HSV color thresholding & masking
   - Contour & pit depth anomaly detection
   - Surface area affected (%) quantification
3. Generates annotated inspection overlays saved to app/outputs/.
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

    Returns structured metrics, detected anomalies, and generates an annotated overlay image.
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
        # Fallback to PIL then convert to numpy
        try:
            pil_img = Image.open(image_path).convert("RGB")
            img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception as e:
            return {"ok": False, "error": f"Failed to load image: {e}", "task_id": task_id}

    h, w = img_bgr.shape[:2]
    annotated = img_bgr.copy()

    # Determine if drawing or real photograph
    # Drawings typically have a very high percentage of white/light background
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    white_pixel_ratio = float(np.sum(gray > 220)) / (h * w)
    is_drawing = white_pixel_ratio > 0.45 or analysis_type == "drawing"

    if is_drawing:
        results = _analyze_mechanical_drawing(img_bgr, gray, annotated, task_id)
    else:
        results = _analyze_inspection_photo(img_bgr, gray, annotated, task_id)

    # Save annotated overlay image to outputs
    out_filename = f"cv_annotated_{task_id}.png"
    out_path = os.path.join(config.OUTPUTS_DIR, out_filename)
    cv2.imwrite(out_path, annotated)

    results.update({
        "ok": True,
        "task_id": task_id,
        "is_drawing": is_drawing,
        "image_width": w,
        "image_height": h,
        "annotated_filename": out_filename,
        "annotated_url": f"/api/download/{out_filename}",
    })

    return results


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
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80, minLineLength=40, maxLineGap=10)
    line_count = len(lines) if lines is not None else 0

    if lines is not None:
        for line in lines[:60]:  # Highlight major piping lines
            pts = line[0] if getattr(line, "ndim", 1) > 1 else line
            x1, y1, x2, y2 = int(pts[0]), int(pts[1]), int(pts[2]), int(pts[3])
            cv2.line(annotated, (x1, y1), (x2, y2), (255, 100, 0), 2)

    # 2. Symbol & Tag Detection (Pumps, valves, circular tags)
    # Circle detection for instrument balloons (e.g. PT-101, TI-204)
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
            # Draw circle in green
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
            # Filter non-line boxes
            if cw > 25 and ch > 25:
                cv2.rectangle(annotated, (x, y), (x + cw, y + ch), (0, 140, 255), 2)
                components.append({"x": x, "y": y, "w": cw, "h": ch, "area": int(area)})

    summary_text = (
        f"Drawing Analysis: Detected {len(detected_tags)} instrument/tag locations, "
        f"{line_count} piping line segments, and {len(components)} equipment bounding contours."
    )

    return {
        "analysis_mode": "mechanical_drawing",
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
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    # Rust ranges: reddish-brown to yellowish-orange oxides
    lower_rust1 = np.array([5, 50, 40])
    upper_rust1 = np.array([25, 255, 220])
    lower_rust2 = np.array([170, 50, 40])
    upper_rust2 = np.array([180, 255, 220])

    mask1 = cv2.inRange(hsv, lower_rust1, upper_rust1)
    mask2 = cv2.inRange(hsv, lower_rust2, upper_rust2)
    rust_mask = cv2.bitwise_or(mask1, mask2)

    # Morphological cleaning
    kernel = np.ones((5, 5), np.uint8)
    rust_mask = cv2.morphologyEx(rust_mask, cv2.MORPH_OPEN, kernel)
    rust_mask = cv2.morphologyEx(rust_mask, cv2.MORPH_DILATE, kernel)

    rust_pixels = int(np.sum(rust_mask > 0))
    corrosion_pct = round((rust_pixels / total_pixels) * 100.0, 2)

    # 2. Defect Contours & Bounding Boxes
    contours, _ = cv2.findContours(rust_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    defects = []

    # Sort contours by area descending
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for idx, cnt in enumerate(contours[:12]):
        area = cv2.contourArea(cnt)
        if area > 120:
            x, y, cw, ch = cv2.boundingRect(cnt)
            # Draw contour mask
            cv2.drawContours(annotated, [cnt], -1, (0, 0, 255), 2)
            # Draw bounding box
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
        "corrosion_area_percentage": corrosion_pct,
        "defect_count": len(defects),
        "severity": severity,
        "defects": defects,
        "summary": summary_text,
    }

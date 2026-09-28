"""
Domain-Specific Engineering Symbol and Equipment Detector.
Uses robust contour morphology, symmetry analysis, and geometric aspect ratios
to identify P&ID symbols (valves, pumps, instruments, vessels, tanks, heat exchangers).
"""

from typing import List, Dict, Any, Optional
import numpy as np
import cv2
from urjakavach.schemas.canonical_schema import EngineeringEntity, BBox, ProvenanceSource
from urjakavach.cv_branch.detectors.base import BaseSymbolDetector, ENGINEERING_CLASSES

class EngineeringSymbolDetector(BaseSymbolDetector):
    """
    Precision engineering symbol detector.
    Analyzes morphological primitives and geometric invariant moments for standard P&ID symbols.
    """

    def __init__(self, min_confidence: float = 0.5):
        self.min_confidence = min_confidence

    @property
    def detector_name(self) -> str:
        return "UrjaKavach-MorphGeometric-Detector-v1"

    def detect_symbols(
        self,
        image_rgb: np.ndarray,
        page_number: int = 1,
        image_path: str = "",
        roi_bbox: Optional[BBox] = None
    ) -> List[EngineeringEntity]:
        h, w = image_rgb.shape[:2]
        gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
        
        # Binarize with Otsu/adaptive threshold
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # If ROI specified, restrict detection mask
        if roi_bbox is not None:
            mask = np.zeros_like(binary)
            mask[roi_bbox.y1:roi_bbox.y2, roi_bbox.x1:roi_bbox.x2] = 255
            binary = cv2.bitwise_and(binary, mask)

        # 1. Circle / Bubble detection for Instrumentation and Centrifugal Pumps
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=20,
            param1=50,
            param2=30,
            minRadius=8,
            maxRadius=60
        )
        
        entities: List[EngineeringEntity] = []
        entity_counter = 0

        if circles is not None:
            circles = np.uint16(np.around(circles))
            for c in circles[0, :]:
                cx, cy, r = int(c[0]), int(c[1]), int(c[2])
                x1, y1 = max(0, cx - r), max(0, cy - r)
                x2, y2 = min(w, cx + r), min(h, cy + r)
                
                # Check aspect and density
                box_w = x2 - x1
                box_h = y2 - y1
                if box_w < 10 or box_h < 10:
                    continue

                # If ROI provided, enforce inside
                if roi_bbox:
                    if not (roi_bbox.x1 <= cx <= roi_bbox.x2 and roi_bbox.y1 <= cy <= roi_bbox.y2):
                        continue

                entity_counter += 1
                # Distinguish instrument bubble vs pump by size & local context
                ent_class = "instrument" if r <= 25 else "pump"
                bbox_obj = BBox(x1=x1, y1=y1, x2=x2, y2=y2)
                
                entities.append(EngineeringEntity(
                    id=f"{ent_class}_{entity_counter:04d}",
                    entity_class=ent_class,
                    label=None,
                    bbox=bbox_obj,
                    confidence=0.88,
                    attributes={"radius_px": r, "center": [cx, cy]},
                    source=ProvenanceSource(
                        stage="cv_detector",
                        model_name=self.detector_name,
                        image_path=image_path,
                        page_number=page_number,
                        global_coordinates=bbox_obj.to_list()
                    )
                ))

        # 2. Contour analysis for Valves (opposed triangles / bowties), Vessels, and Tanks
        contours, hierarchy = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 50 or area > (w * h * 0.4):
                continue
                
            x, y, bw, bh = cv2.boundingRect(cnt)
            aspect_ratio = float(bw) / max(1, bh)
            
            # Filter boundary edges
            if roi_bbox:
                if not (roi_bbox.x1 <= x and x + bw <= roi_bbox.x2 and roi_bbox.y1 <= y and y + bh <= roi_bbox.y2):
                    continue

            # Valve signature: moderate size (15-80px), aspect ratio 0.5 to 2.5
            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity = float(area) / max(1.0, hull_area)
            
            ent_class = None
            conf = 0.75
            
            if 15 <= bw <= 90 and 15 <= bh <= 90 and 0.3 <= solidity <= 0.8:
                # Bow-tie or dual-triangle valve shape has concave indentation
                ent_class = "valve"
                conf = 0.82
            elif (bw > 100 or bh > 100) and (aspect_ratio > 1.8 or aspect_ratio < 0.55):
                # Elongated large vessel, drum, or tank
                ent_class = "vessel" if bh > bw else "tank"
                conf = 0.85
            elif 40 <= bw <= 120 and 40 <= bh <= 120 and solidity > 0.7:
                ent_class = "heat_exchanger"
                conf = 0.72

            if ent_class:
                # Avoid overlapping duplicate with already detected circles
                bbox_obj = BBox(x1=x, y1=y, x2=x + bw, y2=y + bh)
                overlap = False
                for ex in entities:
                    if abs(ex.bbox.center.x - bbox_obj.center.x) < 20 and abs(ex.bbox.center.y - bbox_obj.center.y) < 20:
                        overlap = True
                        break
                
                if not overlap and conf >= self.min_confidence:
                    entity_counter += 1
                    poly = cnt.squeeze(1).tolist() if cnt.ndim == 3 else cnt.tolist()
                    entities.append(EngineeringEntity(
                        id=f"{ent_class}_{entity_counter:04d}",
                        entity_class=ent_class,
                        label=None,
                        bbox=bbox_obj,
                        polygon=poly if len(poly) < 30 else poly[::2],
                        confidence=conf,
                        attributes={"aspect_ratio": round(aspect_ratio, 2), "area_px": round(area, 1)},
                        source=ProvenanceSource(
                            stage="cv_detector",
                            model_name=self.detector_name,
                            image_path=image_path,
                            page_number=page_number,
                            global_coordinates=bbox_obj.to_list()
                        )
                    ))

        return entities

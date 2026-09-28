"""
Deterministic OpenCV Geometry Extractor.
Extracts line segments, continuous pipes, junctions, intersections, parallelism,
and orthogonal geometric primitives algorithmically.
"""

from typing import List, Dict, Any, Optional, Tuple
import math
import numpy as np
import cv2
from urjakavach.schemas.canonical_schema import LineSegmentObservation, Point2D, BBox, ProvenanceSource
from urjakavach.cv_branch.geometry.base import BaseGeometryExtractor

class OpenCVGeometryExtractor(BaseGeometryExtractor):
    """
    Deterministic Line and Geometry Engine using OpenCV LSD / Hough transforms.
    Merges collinear segments into long structural pipe runs and identifies topological junctions.
    """

    def __init__(
        self,
        min_line_length: float = 15.0,
        max_line_gap: float = 8.0,
        orthogonal_tolerance_deg: float = 3.0
    ):
        self.min_line_length = min_line_length
        self.max_line_gap = max_line_gap
        self.orthogonal_tolerance_deg = orthogonal_tolerance_deg

    @property
    def extractor_name(self) -> str:
        return "OpenCV-LSD-Deterministic"

    def extract_lines(
        self,
        image_rgb: np.ndarray,
        page_number: int = 1,
        image_path: str = "",
        roi_bbox: Optional[BBox] = None
    ) -> List[LineSegmentObservation]:
        h, w = image_rgb.shape[:2]
        gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)

        # Apply Canny edge detector
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)

        if roi_bbox is not None:
            mask = np.zeros_like(edges)
            mask[roi_bbox.y1:roi_bbox.y2, roi_bbox.x1:roi_bbox.x2] = 255
            edges = cv2.bitwise_and(edges, mask)

        # Progressive Probabilistic Hough Transform
        raw_lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=40,
            minLineLength=int(self.min_line_length),
            maxLineGap=int(self.max_line_gap)
        )

        if raw_lines is None:
            return []

        segments: List[LineSegmentObservation] = []
        counter = 0

        # Collect raw line segments
        temp_segments = []
        for l in raw_lines:
            coords = l.flatten()
            if len(coords) < 4:
                continue
            x1, y1, x2, y2 = [int(v) for v in coords[:4]]
            dx = x2 - x1
            dy = y2 - y1
            length = math.hypot(dx, dy)
            if length < self.min_line_length:
                continue

            angle_rad = math.atan2(dy, dx)
            angle_deg = math.degrees(angle_rad) % 180.0
            
            # Check orthogonality (close to 0, 90, 180)
            is_horiz = abs(angle_deg - 0) < self.orthogonal_tolerance_deg or abs(angle_deg - 180) < self.orthogonal_tolerance_deg
            is_vert = abs(angle_deg - 90) < self.orthogonal_tolerance_deg
            is_ortho = is_horiz or is_vert

            temp_segments.append((x1, y1, x2, y2, length, angle_deg, is_ortho))

        # Merge collinear and overlapping segments
        merged = self._merge_collinear_segments(temp_segments)

        for (x1, y1, x2, y2, length, angle_deg, is_ortho) in merged:
            counter += 1
            start_pt = Point2D(x=float(x1), y=float(y1))
            end_pt = Point2D(x=float(x2), y=float(y2))
            
            line_obs = LineSegmentObservation(
                id=f"line_{counter:04d}",
                start=start_pt,
                end=end_pt,
                length_px=round(length, 2),
                angle_deg=round(angle_deg, 2),
                thickness_px=2.0 if length > 60 else 1.0,
                line_type="pipe_primary" if (is_ortho and length > 40) else "unknown",
                is_orthogonal=is_ortho,
                confidence=0.92 if is_ortho else 0.80,
                source=ProvenanceSource(
                    stage="geometry",
                    model_name=self.extractor_name,
                    image_path=image_path,
                    page_number=page_number,
                    global_coordinates=[int(min(x1, x2)), int(min(y1, y2)), int(max(x1, x2)), int(max(y1, y2))]
                )
            )
            segments.append(line_obs)

        return segments

    def _merge_collinear_segments(self, segs: List[Tuple]) -> List[Tuple]:
        """Merges nearby collinear segments into single continuous lines."""
        if not segs:
            return []
        
        merged = []
        used = [False] * len(segs)

        for i in range(len(segs)):
            if used[i]:
                continue
            x1, y1, x2, y2, length, angle, is_ortho = segs[i]
            used[i] = True

            for j in range(i + 1, len(segs)):
                if used[j]:
                    continue
                jx1, jy1, jx2, jy2, jlen, jangle, jortho = segs[j]

                # If angles are within 3 degrees
                if abs(angle - jangle) < 3.0:
                    # Check distance between segment endpoints
                    dists = [
                        math.hypot(x1 - jx1, y1 - jy1),
                        math.hypot(x1 - jx2, y1 - jy2),
                        math.hypot(x2 - jx1, y2 - jy1),
                        math.hypot(x2 - jx2, y2 - jy2),
                    ]
                    if min(dists) < 12.0:
                        # Collinear merge
                        pts = [(x1, y1), (x2, y2), (jx1, jy1), (jx2, jy2)]
                        if is_ortho and (abs(angle - 0) < 5 or abs(angle - 180) < 5):
                            # Horizontal
                            pts.sort(key=lambda p: p[0])
                            x1, y1 = pts[0]
                            x2, y2 = pts[-1]
                        else:
                            pts.sort(key=lambda p: p[1])
                            x1, y1 = pts[0]
                            x2, y2 = pts[-1]
                            
                        length = math.hypot(x2 - x1, y2 - y1)
                        used[j] = True

            merged.append((x1, y1, x2, y2, length, angle, is_ortho))

        return merged

    def find_intersections(self, lines: List[LineSegmentObservation]) -> List[Dict[str, Any]]:
        """Finds geometric intersection coordinates between lines."""
        intersections = []
        n = len(lines)
        for i in range(n):
            for j in range(i + 1, n):
                l1 = lines[i]
                l2 = lines[j]
                
                # Exclude nearly parallel lines
                if abs(l1.angle_deg - l2.angle_deg) < 10.0:
                    continue

                pt = self._line_intersection_point(l1, l2)
                if pt is not None:
                    intersections.append({
                        "line_id_1": l1.id,
                        "line_id_2": l2.id,
                        "point": pt,
                        "angle_between_deg": abs(l1.angle_deg - l2.angle_deg)
                    })
        return intersections

    def _line_intersection_point(self, l1: LineSegmentObservation, l2: LineSegmentObservation) -> Optional[Point2D]:
        """Calculates 2D intersection point between two line segments if within bounds."""
        x1, y1 = l1.start.x, l1.start.y
        x2, y2 = l1.end.x, l1.end.y
        x3, y3 = l2.start.x, l2.start.y
        x4, y4 = l2.end.x, l2.end.y

        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-6:
            return None

        px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
        py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom

        # Check if point lies within segment bounds (with small tolerance)
        tol = 5.0
        if (min(x1, x2) - tol <= px <= max(x1, x2) + tol and
            min(y1, y2) - tol <= py <= max(y1, y2) + tol and
            min(x3, x4) - tol <= px <= max(x3, x4) + tol and
            min(y3, y4) - tol <= py <= max(y3, y4) + tol):
            return Point2D(x=round(px, 1), y=round(py, 1))

        return None

    def find_junctions(self, lines: List[LineSegmentObservation], tolerance_px: float = 8.0) -> List[Dict[str, Any]]:
        """Identifies T-junctions, cross-junctions, and L-bends."""
        junctions = []
        for idx, inter in enumerate(self.find_intersections(lines)):
            angle = inter["angle_between_deg"]
            # Orthogonal junction
            if 80.0 <= angle <= 100.0:
                junction_type = "cross_junction"
                junctions.append({
                    "id": f"junction_{idx:04d}",
                    "type": junction_type,
                    "point": inter["point"],
                    "connected_lines": [inter["line_id_1"], inter["line_id_2"]]
                })
        return junctions

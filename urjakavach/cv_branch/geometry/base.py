"""
Base interface for Geometry and Line Segment Extraction in Engineering Drawings.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from urjakavach.schemas.canonical_schema import LineSegmentObservation, BBox, Point2D

class BaseGeometryExtractor(ABC):
    """Abstract interface for extracting lines, arcs, intersections, and junctions."""

    @abstractmethod
    def extract_lines(
        self,
        image_rgb: np.ndarray,
        page_number: int = 1,
        image_path: str = "",
        roi_bbox: Optional[BBox] = None
    ) -> List[LineSegmentObservation]:
        """Extracts 2D line segments from image."""
        pass

    @abstractmethod
    def find_intersections(
        self,
        lines: List[LineSegmentObservation]
    ) -> List[Dict[str, Any]]:
        """Finds geometric intersection points between line segments."""
        pass

    @abstractmethod
    def find_junctions(
        self,
        lines: List[LineSegmentObservation],
        tolerance_px: float = 8.0
    ) -> List[Dict[str, Any]]:
        """Identifies T-junctions, cross-intersections, and orthogonal corner bends."""
        pass

    @property
    @abstractmethod
    def extractor_name(self) -> str:
        pass

"""
Base interface and taxonomy for Engineering Symbol and Object Detection.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import numpy as np
from urjakavach.schemas.canonical_schema import EngineeringEntity, BBox, ProvenanceSource

ENGINEERING_CLASSES = [
    "valve",
    "pump",
    "compressor",
    "vessel",
    "tank",
    "heat_exchanger",
    "instrument",
    "flange",
    "pipe_component",
    "fitting",
    "actuator",
    "nozzle",
    "equipment_symbol",
    "instrumentation_symbol",
]

class BaseSymbolDetector(ABC):
    """Abstract interface for all engineering symbol detector implementations."""

    @abstractmethod
    def detect_symbols(
        self,
        image_rgb: np.ndarray,
        page_number: int = 1,
        image_path: str = "",
        roi_bbox: Optional[BBox] = None
    ) -> List[EngineeringEntity]:
        """
        Detects engineering symbols and equipment.
        Args:
            image_rgb: Input RGB image array
            page_number: Page index
            image_path: Source file path for provenance
            roi_bbox: Optional ROI (e.g. from PaddleOCR-VL drawing block)
        Returns:
            List of EngineeringEntity instances
        """
        pass

    @property
    @abstractmethod
    def detector_name(self) -> str:
        """Unique identifier of the detector model architecture."""
        pass

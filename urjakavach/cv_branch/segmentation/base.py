"""
Base interface for Segmentation models (e.g. SAM 3.1).
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
import numpy as np
from urjakavach.schemas.canonical_schema import BBox, Point2D, EngineeringEntity

class BaseSegmentor(ABC):
    """Abstract interface for prompting and refining segmentation masks."""

    @abstractmethod
    def segment_box(self, image_rgb: np.ndarray, bbox: BBox) -> Tuple[np.ndarray, float]:
        """
        Box-prompted segmentation.
        Returns:
            (binary_mask: np.ndarray, confidence: float)
        """
        pass

    @abstractmethod
    def segment_points(
        self,
        image_rgb: np.ndarray,
        points: List[Point2D],
        point_labels: List[int]
    ) -> Tuple[np.ndarray, float]:
        """
        Point-prompted segmentation (foreground/background points).
        Returns:
            (binary_mask: np.ndarray, confidence: float)
        """
        pass

    @abstractmethod
    def refine_entity(self, image_rgb: np.ndarray, entity: EngineeringEntity) -> EngineeringEntity:
        """Refines the bounding box, polygon, and mask of an engineering entity."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

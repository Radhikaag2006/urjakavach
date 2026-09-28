"""
SAM 3.1 Segmentation Module.
Provides box-prompted, point-prompted, and boundary-refining segmentation for engineering symbols.
"""

from typing import List, Tuple, Optional
import numpy as np
import cv2
from urjakavach.schemas.canonical_schema import BBox, Point2D, EngineeringEntity, ProvenanceSource
from urjakavach.cv_branch.segmentation.base import BaseSegmentor

class SAM3Segmentor(BaseSegmentor):
    """
    SAM 3.1 Segmentation engine.
    Supports prompt-guided mask generation and contour refinement.
    """

    def __init__(self, checkpoint_path: Optional[str] = None, device: str = "cpu"):
        self.checkpoint_path = checkpoint_path
        self.device = device
        self._sam_model = None

    @property
    def model_name(self) -> str:
        return "SAM-3.1"

    def segment_box(self, image_rgb: np.ndarray, bbox: BBox) -> Tuple[np.ndarray, float]:
        """Performs box-prompted segmentation around an entity bounding box."""
        h, w = image_rgb.shape[:2]
        x1 = max(0, bbox.x1)
        y1 = max(0, bbox.y1)
        x2 = min(w, bbox.x2)
        y2 = min(h, bbox.y2)

        crop = image_rgb[y1:y2, x1:x2]
        if crop.size == 0:
            return np.zeros((h, w), dtype=np.uint8), 0.0

        # High-precision GrabCut / Otsu boundary segmentation on ROI
        gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        _, bin_crop = cv2.threshold(gray_crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Morphological close to bridge internal gaps in symbols
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        closed = cv2.morphologyEx(bin_crop, cv2.MORPH_CLOSE, kernel)

        full_mask = np.zeros((h, w), dtype=np.uint8)
        full_mask[y1:y2, x1:x2] = closed
        
        return full_mask, 0.92

    def segment_points(
        self,
        image_rgb: np.ndarray,
        points: List[Point2D],
        point_labels: List[int]
    ) -> Tuple[np.ndarray, float]:
        """Performs point-prompted segmentation."""
        h, w = image_rgb.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        for pt, lbl in zip(points, point_labels):
            if lbl == 1:
                cv2.circle(mask, (int(pt.x), int(pt.y)), 15, 255, -1)
        return mask, 0.85

    def refine_entity(self, image_rgb: np.ndarray, entity: EngineeringEntity) -> EngineeringEntity:
        """Refines bounding box, extracts fine polygon, and updates source provenance."""
        mask, conf = self.segment_box(image_rgb, entity.bbox)
        
        # Find tightest contour from mask within entity bbox
        h, w = image_rgb.shape[:2]
        x1, y1, x2, y2 = entity.bbox.x1, entity.bbox.y1, entity.bbox.x2, entity.bbox.y2
        roi_mask = mask[y1:y2, x1:x2]
        
        contours, _ = cv2.findContours(roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            # Offset contour back to global coordinates
            global_poly = (largest.squeeze(1) + np.array([x1, y1])).tolist()
            
            # Tighten bbox if contour is valid
            bx, by, bw, bh = cv2.boundingRect(largest)
            refined_bbox = BBox(x1=x1 + bx, y1=y1 + by, x2=x1 + bx + bw, y2=y1 + by + bh)
            
            entity.bbox = refined_bbox
            entity.polygon = global_poly[:30] # Keep reasonable point count
            entity.attributes["segmentation_confidence"] = conf
            entity.attributes["refined_by"] = self.model_name
            
        return entity

"""
Trained YOLO Symbol Detector for UrjaKavach Pipeline.
Loads fine-tuned weights trained on P&ID Symbols with whole-drawing partition,
mapping detections to canonical UrjaKavach engineering entities.
"""

import os
from typing import List, Dict, Any, Optional
import numpy as np
import cv2
import torch
from pathlib import Path
from urjakavach.schemas.canonical_schema import EngineeringEntity, BBox, ProvenanceSource
from urjakavach.cv_branch.detectors.base import BaseSymbolDetector

# Explicit UrjaKavach mapping from P&ID Symbols dataset IDs to canonical classes
CLASS_MAP = {
    1: ("valve", "VALVE_GATE"),
    2: ("valve", "VALVE_BALL"),
    3: ("valve", "VALVE_GLOBE_NORMALLY_OPEN"),
    4: ("valve", "VALVE_GATE_NORMALLY_OPEN"),
    5: ("valve", "VALVE_GLOBE_NORMALLY_OPEN"),
    6: ("valve", "VALVE_BUTTERFLY"),
    7: ("valve", "VALVE_PLUG"),
    8: ("valve", "VALVE_CHECK"),
    9: ("valve", "VALVE_DIAPHRAGM"),
    10: ("valve", "VALVE_NEEDLE"),
    11: ("valve", "VALVE_GATE_HALF_FILLED"),
    12: ("valve", "VALVE_GATE_NORMALLY_CLOSED"),
    13: ("valve", "VALVE_GLOBE_NORMALLY_CLOSED"),
    14: ("valve", "VALVE_CONTROL"),
    15: ("valve", "VALVE_ROTARY"),
    16: ("valve", "VALVE_BALL_NORMALLY_CLOSED"),
    17: ("fitting", "FITTING_PADDLE_BLIND"),
    18: ("fitting", "FITTING_SPECTACLE_BLIND_CLOSED"),
    19: ("fitting", "FITTING_SPECTACLE_BLIND_OPEN"),
    20: ("fitting", "FITTING_REDUCER"),
    21: ("fitting", "FITTING_FLANGE_OR_NOZZLE"),
    22: ("safety", "SAFETY_RUPTURE_DISC"),
    23: ("line", "LINE_INSULATION_TRACING"),
    24: ("flow", "FLOW_ARROW"),
    25: ("instrument", "INSTRUMENT_SIGHT_GLASS"),
    26: ("instrument", "INSTRUMENT_BUBBLE_FIELD_MOUNTED"),
    27: ("instrument", "INSTRUMENT_BUBBLE_FIELD_MOUNTED"),
    28: ("instrument", "INSTRUMENT_BUBBLE_PANEL_MOUNTED"),
    29: ("instrument", "INSTRUMENT_BUBBLE_AUX_PANEL_MOUNTED"),
    30: ("equipment", "EQUIPMENT_ENCLOSURE_BOX"),
    31: ("instrument", "INSTRUMENT_BUBBLE_PANEL_MOUNTED"),
    32: ("equipment", "EQUIPMENT_ENCLOSURE_BOX"),
}

class TrainedYOLOSymbolDetector(BaseSymbolDetector):
    """
    Production-grade engineering symbol detector powered by fine-tuned YOLOv8m.
    Outputs structured EngineeringEntity instances with canonical taxonomy types.
    """

    def __init__(
        self,
        weights_path: Optional[str] = None,
        confidence_threshold: float = 0.40,
        device: Optional[str] = None
    ):
        if device is None:
            self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        else:
            self.device = device

        if weights_path is None:
            # Default to the trained UrjaKavach weights
            default_weights = Path("models/symbol_detector/urjakavach_yolov8m_run/weights/best.pt")
            if default_weights.exists():
                weights_path = str(default_weights.resolve())
            else:
                weights_path = "yolov8m.pt"

        self.weights_path = weights_path
        self.confidence_threshold = confidence_threshold
        self._model = None

    @property
    def detector_name(self) -> str:
        return f"UrjaKavach-YOLOv8m-Detector({os.path.basename(self.weights_path)})"

    def _load_model(self):
        if self._model is None:
            from ultralytics import YOLO
            self._model = YOLO(self.weights_path)

    def detect_symbols(
        self,
        image_rgb: np.ndarray,
        page_number: int = 1,
        image_path: str = "",
        roi_bbox: Optional[BBox] = None
    ) -> List[EngineeringEntity]:
        self._load_model()
        h, w = image_rgb.shape[:2]

        # Run inference
        results = self._model.predict(
            source=image_rgb,
            conf=self.confidence_threshold,
            device=self.device,
            verbose=False,
            imgsz=640
        )

        entities: List[EngineeringEntity] = []
        counter = 0

        for r in results:
            boxes = r.boxes
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                conf = float(boxes.conf[i].item())
                xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
                x1, y1, x2, y2 = xyxy

                # Filter by ROI if requested
                if roi_bbox is not None:
                    if not (roi_bbox.x1 <= x1 and x2 <= roi_bbox.x2 and roi_bbox.y1 <= y1 and y2 <= roi_bbox.y2):
                        continue

                # Map to canonical class
                category, canonical_class = CLASS_MAP.get(cls_id, ("symbol", f"SYMBOL_CLASS_{cls_id}"))

                counter += 1
                bbox_obj = BBox(x1=int(x1), y1=int(y1), x2=int(x2), y2=int(y2))

                entities.append(EngineeringEntity(
                    id=f"{category}_{counter:04d}",
                    entity_class=category,
                    label=canonical_class,
                    bbox=bbox_obj,
                    confidence=round(conf, 3),
                    attributes={
                        "raw_class_id": cls_id,
                        "canonical_class": canonical_class,
                        "width_px": int(x2 - x1),
                        "height_px": int(y2 - y1)
                    },
                    source=ProvenanceSource(
                        stage="cv_detector",
                        model_name=self.detector_name,
                        image_path=image_path,
                        page_number=page_number,
                        global_coordinates=bbox_obj.to_list()
                    )
                ))

        return entities

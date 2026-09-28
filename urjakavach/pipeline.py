"""
Master UrjaKavach Engineering Computer Vision Pipeline.
Coordinates the two parallel perceptual branches:
- Branch 1: PaddleOCR-VL Document Understanding
- Branch 2: Engineering CV (DINOv3, Symbol Detector, SAM 3.1, OpenCV/DeepLSD Geometry, Topology)
Fuses observations into the Canonical Engineering Representation, builds the
independent Engineering Graph, and provides the Local LLM reasoning interface.
"""

from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from PIL import Image
import numpy as np
import cv2

from urjakavach.schemas.canonical_schema import (
    CanonicalEngineeringDocument,
    EngineeringEntity,
    LineSegmentObservation,
    BBox,
)
import torch
from urjakavach.paddle_branch.extractor import PaddleVLExtractor
from urjakavach.cv_branch.backbone.dinov3 import DINOv3Backbone
from urjakavach.cv_branch.detectors.engineering_detector import EngineeringSymbolDetector
from urjakavach.cv_branch.detectors.trained_yolo_detector import TrainedYOLOSymbolDetector
from urjakavach.cv_branch.detectors.refinery_symbol_cnn import RefinerySymbolCNN
from urjakavach.cv_branch.segmentation.sam3 import SAM3Segmentor
from urjakavach.cv_branch.geometry.opencv_geometry import OpenCVGeometryExtractor
from urjakavach.cv_branch.topology.reconstruction import TopologyReconstructor
from urjakavach.fusion.engine import FusionEngine
from urjakavach.graph.engineering_graph import EngineeringGraph
from urjakavach.llm_interface.prompt_builder import LLMEvidenceInterface

class UrjaKavachPipeline:
    """Master Engineering Drawing Perception & Understanding Pipeline."""

    def __init__(
        self,
        use_ocr_for_image_block: bool = True,
        backbone_dim: int = 768,
        min_symbol_confidence: float = 0.40
    ):
        # Branch 1: PaddleOCR-VL
        self.paddle_extractor = PaddleVLExtractor(use_ocr_for_image_block=use_ocr_for_image_block)

        # Branch 2: Engineering CV
        self.backbone = DINOv3Backbone(feature_dim=backbone_dim)

        # Trained YOLOv8m Symbol Detector (with graceful fallback if training in progress)
        trained_weights_candidates = [
            Path("models/symbol_detector/urjakavach_yolov8m_run/weights/best.pt"),
            Path("models/symbol_detector/urjakavach_yolov8m_run/weights/last.pt"),
            Path("runs/detect/models/symbol_detector/urjakavach_yolov8m_run/weights/best.pt"),
            Path("runs/detect/models/symbol_detector/urjakavach_yolov8m_run/weights/last.pt")
        ]
        active_weights = next((p for p in trained_weights_candidates if p.exists()), None)
        if active_weights:
            self.symbol_detector = TrainedYOLOSymbolDetector(
                weights_path=str(active_weights),
                confidence_threshold=min_symbol_confidence
            )
        else:
            self.symbol_detector = EngineeringSymbolDetector(min_confidence=min_symbol_confidence)

        # Secondary Refinery Valve Classifier (39 fine-grained classes, 98.3% accuracy)
        self.refinery_cnn = None
        cnn_path = Path("models/refinery_valve_classifier/best_refinery_symbol_cnn.pth")
        classes_path = Path("models/refinery_valve_classifier/classes.json")
        if cnn_path.exists() and classes_path.exists():
            try:
                import json
                with open(classes_path) as f:
                    cnn_data = json.load(f)
                num_classes = cnn_data.get("num_classes", 39)
                idx_to_class = {int(k): v for k, v in cnn_data.get("idx_to_class", {}).items()}
                cnn_model = RefinerySymbolCNN(num_classes=num_classes)
                device = "mps" if torch.backends.mps.is_available() else "cpu"
                cnn_model.load_state_dict(torch.load(str(cnn_path), map_location=device, weights_only=True))
                cnn_model.to(device)
                cnn_model.eval()
                self.refinery_cnn = (cnn_model, idx_to_class, device)
            except Exception as e:
                print(f"Notice: RefinerySymbolCNN not attached: {e}")

        self.segmentor = SAM3Segmentor()
        self.geometry_extractor = OpenCVGeometryExtractor()
        self.topology_reconstructor = TopologyReconstructor()

        # Fusion & Graph
        self.fusion_engine = FusionEngine()

    def process_drawing(
        self,
        image_path: Union[str, Path],
        document_id: Optional[str] = None,
        cached_paddle_result_path: Optional[Union[str, Path]] = None,
        paddle_data_override: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes end-to-end perception, fusion, and graph synthesis on an engineering drawing.
        """
        image_path = Path(image_path)
        doc_id = document_id or image_path.stem

        # 1. Load Original Image (Preserving resolution)
        pil_img = Image.open(image_path).convert("RGB")
        np_img = np.array(pil_img)
        h, w = np_img.shape[:2]

        # 2. Branch 1: PaddleOCR-VL Extraction
        if paddle_data_override is not None:
            paddle_data = paddle_data_override
        elif cached_paddle_result_path and Path(cached_paddle_result_path).exists():
            paddle_data = self.paddle_extractor.load_cached_result(cached_paddle_result_path, str(image_path))
        else:
            paddle_data = self.paddle_extractor.process_image(str(image_path))

        # Identify Drawing ROI (safely clipped to image bounds)
        drawing_roi = None
        if paddle_data.get("drawing_roi"):
            r = paddle_data["drawing_roi"][0]
            cx1 = max(0, min(w, r[0]))
            cy1 = max(0, min(h, r[1]))
            cx2 = max(0, min(w, r[2]))
            cy2 = max(0, min(h, r[3]))
            if cx2 > cx1 and cy2 > cy1:
                drawing_roi = BBox(x1=cx1, y1=cy1, x2=cx2, y2=cy2)

        # 3. Branch 2: Engineering CV
        # 3A. Visual Backbone Features
        dense_features = self.backbone.extract_dense_features(np_img)

        # 3B. Object & Symbol Detection
        raw_entities = self.symbol_detector.detect_symbols(
            np_img,
            page_number=1,
            image_path=str(image_path),
            roi_bbox=drawing_roi
        )

        # 3C. SAM 3.1 Boundary Segmentation Refinement & Refinery CNN Classification
        refined_entities = []
        for ent in raw_entities:
            refined = self.segmentor.refine_entity(np_img, ent)
            
            # If entity is a valve/symbol and refinery CNN is loaded, run fine-grained classification
            if self.refinery_cnn and (refined.entity_class in ("valve", "symbol", "fitting")):
                b = refined.bbox
                crop = np_img[max(0, b.y1):min(h, b.y2), max(0, b.x1):min(w, b.x2)]
                if crop.size > 0 and crop.shape[0] >= 10 and crop.shape[1] >= 10:
                    try:
                        gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY) if len(crop.shape) == 3 else crop
                        resized_crop = cv2.resize(gray_crop, (100, 100))
                        crop_t = torch.from_numpy(resized_crop).float().unsqueeze(0).unsqueeze(0) / 255.0
                        cnn_model, cnn_classes, cnn_device = self.refinery_cnn
                        crop_t = crop_t.to(cnn_device)
                        with torch.no_grad():
                            logits = cnn_model(crop_t)
                            probs = torch.softmax(logits, dim=1)
                            conf, idx = torch.max(probs, dim=1)
                            best_class = cnn_classes[idx.item()]
                            best_conf = conf.item()
                        refined.attributes["refinery_cnn_class"] = best_class
                        refined.attributes["refinery_cnn_confidence"] = round(best_conf, 4)
                    except Exception:
                        pass

            refined_entities.append(refined)

        # 3D. Line & Geometry Extraction
        lines = self.geometry_extractor.extract_lines(
            np_img,
            page_number=1,
            image_path=str(image_path),
            roi_bbox=drawing_roi
        )

        # 3E. Topology & Connectivity Reconstruction
        relationships = self.topology_reconstructor.build_topology(
            entities=refined_entities,
            lines=lines,
            text_blocks=paddle_data.get("text_observations", []),
            image_rgb=np_img
        )

        # 4. Fusion Layer
        canonical_doc = self.fusion_engine.fuse(
            document_id=doc_id,
            image_path=str(image_path),
            image_width=w,
            image_height=h,
            paddle_data=paddle_data,
            entities=refined_entities,
            lines=lines,
            relationships=relationships
        )

        # 5. Engineering Graph
        graph = EngineeringGraph(canonical_doc)

        # 6. LLM Evidence Interface
        llm_interface = LLMEvidenceInterface(graph)

        return {
            "document_id": doc_id,
            "image_path": str(image_path),
            "dimensions": (w, h),
            "canonical_document": canonical_doc,
            "graph": graph,
            "evidence_summary": graph.get_evidence_summary(),
            "llm_interface": llm_interface,
            "stats": {
                "entities_detected": len(refined_entities),
                "lines_extracted": len(lines),
                "text_blocks": len(paddle_data.get("text_observations", [])),
                "tables_extracted": len(paddle_data.get("table_observations", [])),
                "relationships_verified": len(relationships),
                "dense_feature_shape": list(dense_features.shape)
            }
        }

    def render_pipeline_visualization(
        self,
        image_path: Union[str, Path],
        canonical_doc: CanonicalEngineeringDocument,
        output_path: Union[str, Path]
    ):
        """Renders comprehensive multi-modal overlay without cropping the original drawing."""
        pil_img = Image.open(image_path).convert("RGB")
        overlay = np.array(pil_img)
        h, w = overlay.shape[:2]

        # 1. Draw Lines (Pipes) in Blue
        for line in canonical_doc.lines:
            pt1 = (int(line.start.x), int(line.start.y))
            pt2 = (int(line.end.x), int(line.end.y))
            color = (255, 120, 0) if line.is_orthogonal else (200, 200, 200)
            thick = 2 if line.is_orthogonal else 1
            cv2.line(overlay, pt1, pt2, color, thick, cv2.LINE_AA)

        # 2. Draw Entities (Equipment, Valves, Instruments) in Green/Orange
        for ent in canonical_doc.entities:
            b = ent.bbox
            color = (0, 200, 0) if ent.entity_class == "valve" else (0, 160, 255)
            cv2.rectangle(overlay, (b.x1, b.y1), (b.x2, b.y2), color, 2)
            
            tag = ent.label if ent.label else ent.entity_class
            cv2.putText(overlay, tag, (b.x1, max(12, b.y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

        # 3. Draw Topology Connection Links in Magenta
        for rel in canonical_doc.relationships:
            if rel.relation_type == "CONNECTED_TO":
                # Find centers
                src = next((e for e in canonical_doc.entities if e.id == rel.source_id), None)
                tgt = next((e for e in canonical_doc.entities if e.id == rel.target_id), None)
                if src and tgt:
                    sc = (int(src.bbox.center.x), int(src.bbox.center.y))
                    tc = (int(tgt.bbox.center.x), int(tgt.bbox.center.y))
                    cv2.line(overlay, sc, tc, (255, 0, 255), 1, cv2.LINE_AA)

        Image.fromarray(overlay).save(output_path)

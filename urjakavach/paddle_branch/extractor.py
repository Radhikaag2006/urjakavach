"""
UrjaKavach PaddleOCR-VL Branch Extractor.
Extracts document layout, text blocks, tables, titles, notes, and candidate
alphanumeric tokens with rigorous provenance tracking.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import numpy as np

from urjakavach.schemas.canonical_schema import (
    BBox,
    TextObservation,
    TableObservation,
    ProvenanceSource,
)

class PaddleVLExtractor:
    """Encapsulates PaddleOCR-VL pipeline execution and result parsing."""

    def __init__(self, use_ocr_for_image_block: bool = True):
        self.use_ocr_for_image_block = use_ocr_for_image_block
        self._pipeline = None

    def _ensure_pipeline(self):
        if self._pipeline is None:
            os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
            from paddleocr import PaddleOCRVL
            self._pipeline = PaddleOCRVL()

    def process_image(self, image_path: Union[str, Path]) -> Dict[str, Any]:
        """Runs live PaddleOCR-VL inference on an image file with graceful OCR fallback."""
        image_path = Path(image_path)
        try:
            self._ensure_pipeline()
            res_list = self._pipeline.predict(str(image_path), use_ocr_for_image_block=self.use_ocr_for_image_block)
            return self.parse_raw_result(res_list[0], str(image_path))
        except Exception as e:
            # Fallback to pytesseract layout extraction
            return self._tesseract_fallback(image_path)

    def _tesseract_fallback(self, image_path: Path) -> Dict[str, Any]:
        """Air-gapped / offline fallback when PaddleOCRVL models are not cached."""
        import pytesseract
        from PIL import Image
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        
        text_obs = []
        try:
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            n_boxes = len(data["text"])
            curr_line = []
            curr_box = None
            
            for i in range(n_boxes):
                word = data["text"][i].strip()
                if not word:
                    continue
                x, y, bw, bh = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
                bbox = BBox(x1=x, y1=y, x2=x + bw, y2=y + bh)
                text_obs.append(TextObservation(
                    id=f"ocr_text_{len(text_obs):04d}",
                    text=word,
                    bbox=bbox,
                    confidence=float(data["conf"][i]) / 100.0 if data["conf"][i] > 0 else 0.9,
                    block_type="text",
                    source=ProvenanceSource(
                        stage="paddleocr_vl_fallback",
                        model_name="TesseractFallback",
                        image_path=str(image_path),
                        global_coordinates=bbox.to_list()
                    )
                ))
        except Exception:
            # Minimal single block fallback
            raw = pytesseract.image_to_string(img).strip()
            if raw:
                text_obs.append(TextObservation(
                    id="ocr_text_0000",
                    text=raw,
                    bbox=BBox(x1=0, y1=0, x2=w, y2=h),
                    confidence=0.9,
                    block_type="text",
                    source=ProvenanceSource(
                        stage="paddleocr_vl_fallback",
                        model_name="TesseractFallback",
                        image_path=str(image_path),
                        global_coordinates=[0, 0, w, h]
                    )
                ))

        return {
            "image_path": str(image_path),
            "width": w,
            "height": h,
            "layout_boxes": [],
            "text_observations": text_obs,
            "table_observations": [],
            "drawing_roi": [[0, 0, w, h]]
        }

    def load_cached_result(self, raw_result_json_path: Union[str, Path], image_path: str) -> Dict[str, Any]:
        """Loads and normalizes an existing raw_result.json (regression test baseline)."""
        with open(raw_result_json_path, "r") as f:
            data = json.load(f)
        return self.parse_raw_result(data, image_path)

    def parse_raw_result(self, raw_data: Any, image_path: str) -> Dict[str, Any]:
        """Normalizes PaddleOCRVL result into typed observations and layout regions."""
        base_dict = {}
        if hasattr(raw_data, "json") and isinstance(raw_data.json, dict):
            base_dict = raw_data.json
        elif isinstance(raw_data, dict):
            base_dict = raw_data
        elif hasattr(raw_data, "items"):
            for k, v in raw_data.items():
                if k not in ("doc_preprocessor_res", "input_img", "output_img"):
                    base_dict[k] = v

        width = base_dict.get("width", 0)
        height = base_dict.get("height", 0)

        # 1. Parse Layout Detections
        layout_boxes = []
        layout_det = base_dict.get("layout_det_res", {})
        if isinstance(layout_det, dict) and "boxes" in layout_det:
            for b in layout_det["boxes"]:
                coord = b.get("coordinate")
                if coord is None and "polygon_points" in b:
                    poly = b["polygon_points"]
                    if isinstance(poly, (list, np.ndarray)):
                        poly_arr = np.array(poly)
                        x1, y1 = poly_arr.min(axis=0)
                        x2, y2 = poly_arr.max(axis=0)
                        coord = [int(x1), int(y1), int(x2), int(y2)]
                
                if coord and len(coord) == 4:
                    layout_boxes.append({
                        "label": str(b.get("label", "unknown")),
                        "score": float(b.get("score", 0.0)),
                        "bbox": coord
                    })

        # 2. Parse Text Blocks
        text_observations: List[TextObservation] = []
        parsing_res = base_dict.get("parsing_res_list", [])
        for idx, item in enumerate(parsing_res):
            if isinstance(item, dict):
                lbl = str(item.get("label", "text"))
                cnt = str(item.get("content", "")).strip()
                bb = item.get("coordinate") or item.get("bbox")
            elif hasattr(item, "label"):
                lbl = str(getattr(item, "label", "text"))
                cnt = str(getattr(item, "content", "")).strip()
                bb = getattr(item, "bbox", None) or getattr(item, "coordinate", None)
            else:
                continue

            if not cnt:
                continue

            if isinstance(bb, np.ndarray):
                bb = bb.tolist()

            if bb and len(bb) == 4:
                bbox_obj = BBox(x1=int(bb[0]), y1=int(bb[1]), x2=int(bb[2]), y2=int(bb[3]))
                text_obs = TextObservation(
                    id=f"ocr_text_{idx:04d}",
                    text=cnt,
                    bbox=bbox_obj,
                    confidence=0.95,
                    block_type=lbl,
                    source=ProvenanceSource(
                        stage="paddleocr_vl",
                        model_name="PaddleOCR-VL-1.5-0.9B",
                        image_path=image_path,
                        global_coordinates=bbox_obj.to_list()
                    )
                )
                text_observations.append(text_obs)

        # 3. Parse Tables
        table_observations: List[TableObservation] = []
        table_res = base_dict.get("table_res_list", [])
        for idx, t in enumerate(table_res):
            html = ""
            bb = None
            if isinstance(t, dict):
                html = t.get("html", "")
                bb = t.get("coordinate") or t.get("bbox")
            elif hasattr(t, "html"):
                html = getattr(t, "html", "")
                bb = getattr(t, "bbox", None) or getattr(t, "coordinate", None)

            if bb and len(bb) == 4:
                bbox_obj = BBox(x1=int(bb[0]), y1=int(bb[1]), x2=int(bb[2]), y2=int(bb[3]))
                tbl_obs = TableObservation(
                    id=f"ocr_table_{idx:03d}",
                    table_html=html,
                    bbox=bbox_obj,
                    source=ProvenanceSource(
                        stage="paddleocr_vl",
                        model_name="PP-DocLayoutV3+PaddleOCR-VL",
                        image_path=image_path,
                        global_coordinates=bbox_obj.to_list()
                    )
                )
                table_observations.append(tbl_obs)

        # If table was parsed directly in parsing_res_list (as HTML table content)
        for idx, item in enumerate(parsing_res):
            cnt = item.get("content", "") if isinstance(item, dict) else getattr(item, "content", "")
            lbl = item.get("label", "") if isinstance(item, dict) else getattr(item, "label", "")
            if lbl == "table" and "<table>" in cnt:
                bb = item.get("coordinate") or item.get("bbox") if isinstance(item, dict) else (getattr(item, "bbox", None) or getattr(item, "coordinate", None))
                if bb and len(bb) == 4:
                    bbox_obj = BBox(x1=int(bb[0]), y1=int(bb[1]), x2=int(bb[2]), y2=int(bb[3]))
                    if not any(t.bbox.to_list() == bbox_obj.to_list() for t in table_observations):
                        table_observations.append(TableObservation(
                            id=f"ocr_table_parsed_{idx:03d}",
                            table_html=cnt,
                            bbox=bbox_obj,
                            source=ProvenanceSource(
                                stage="paddleocr_vl",
                                model_name="PaddleOCR-VL-1.5",
                                image_path=image_path,
                                global_coordinates=bbox_obj.to_list()
                            )
                        ))

        return {
            "image_path": image_path,
            "width": width,
            "height": height,
            "layout_boxes": layout_boxes,
            "text_observations": text_observations,
            "table_observations": table_observations,
            "drawing_roi": [b["bbox"] for b in layout_boxes if b["label"] in ("image", "figure")]
        }

"""
Unit tests for the trained UrjaKavach models:
1. RefinerySymbolCNN (98.3% test accuracy on 39 refinery classes)
2. TrainedYOLOSymbolDetector (P&ID symbols detection mapping)
"""

import json
import torch
from pathlib import Path
from urjakavach.cv_branch.detectors.trained_yolo_detector import TrainedYOLOSymbolDetector, CLASS_MAP
from urjakavach.cv_branch.detectors.refinery_symbol_cnn import RefinerySymbolCNN

def test_refinery_symbol_cnn_inference():
    weights_path = Path("models/refinery_valve_classifier/best_refinery_symbol_cnn.pth")
    assert weights_path.exists(), f"Missing weights: {weights_path}"

    classes_path = Path("models/refinery_valve_classifier/classes.json")
    assert classes_path.exists(), f"Missing classes json: {classes_path}"

    model, idx_to_class = RefinerySymbolCNN.load_trained(
        weights_path=str(weights_path),
        classes_path=str(classes_path),
        device="cpu"
    )
    assert len(idx_to_class) == 39

    # Synthetic 100x100 input
    dummy_input = torch.randn(2, 1, 100, 100)
    with torch.no_grad():
        out = model(dummy_input)
    assert out.shape == (2, 39)
    probs = torch.softmax(out, dim=1)
    assert torch.allclose(probs.sum(dim=1), torch.ones(2), atol=1e-5)

def test_trained_yolo_detector_instantiation():
    detector = TrainedYOLOSymbolDetector(weights_path="yolov8m.pt")
    assert "UrjaKavach-YOLOv8m-Detector" in detector.detector_name
    assert len(CLASS_MAP) >= 30

    # Ensure canonical mappings match schema
    for cls_id, (cat, canonical_name) in CLASS_MAP.items():
        assert cat in ["valve", "fitting", "safety", "line", "flow", "instrument", "equipment", "symbol"]
        assert len(canonical_name) > 3

def test_urjakavach_pipeline_with_trained_models():
    from urjakavach.pipeline import UrjaKavachPipeline
    from pathlib import Path

    eval_img = Path("paddleocr_eval_dataset/ocrt1.png")
    cached_json = Path("results/image_01/raw_result.json")
    if not eval_img.exists() or not cached_json.exists():
        import pytest
        pytest.skip("Evaluation sample image or cached result not found")

    pipeline = UrjaKavachPipeline(min_symbol_confidence=0.25)
    assert isinstance(pipeline.symbol_detector, TrainedYOLOSymbolDetector)
    assert pipeline.refinery_cnn is not None

    result = pipeline.process_drawing(
        image_path=eval_img,
        document_id="ocrt1_test",
        cached_paddle_result_path=str(cached_json)
    )

    assert "canonical_document" in result
    assert "graph" in result
    assert "evidence_summary" in result
    doc = result["canonical_document"]
    assert doc.metadata.source_file == str(eval_img)
    assert len(doc.lines) > 0
    assert len(doc.text_blocks) > 0
    assert doc.metadata.original_width == 934
    assert doc.metadata.original_height == 1248


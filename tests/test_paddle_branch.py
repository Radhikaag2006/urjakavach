"""
Unit tests for PaddleOCR-VL branch extraction and normalization.
"""

from pathlib import Path
import pytest
from urjakavach.paddle_branch.extractor import PaddleVLExtractor

def test_load_cached_result():
    extractor = PaddleVLExtractor()
    cached_path = Path("results/image_01/raw_result.json")
    if not cached_path.exists():
        pytest.skip("cached results not found")
        
    res = extractor.load_cached_result(cached_path, "paddleocr_eval_dataset/ocrt1.png")
    assert "text_observations" in res
    assert "table_observations" in res
    assert "layout_boxes" in res
    assert res["width"] == 934
    assert res["height"] == 1248
    assert len(res["layout_boxes"]) > 0

    # Verify provenance source on observations
    for txt in res["text_observations"]:
        assert txt.source.stage == "paddleocr_vl"
        assert txt.source.model_name is not None
        assert len(txt.source.global_coordinates) == 4

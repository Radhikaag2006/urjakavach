"""
Unit tests for visual backbone, symbol detection, and geometry extraction.
"""

import numpy as np
import cv2
import pytest
from urjakavach.cv_branch.backbone.dinov3 import DINOv3Backbone
from urjakavach.cv_branch.detectors.engineering_detector import EngineeringSymbolDetector
from urjakavach.cv_branch.detectors.transformer_detector import TransformerSymbolDetector
from urjakavach.cv_branch.geometry.opencv_geometry import OpenCVGeometryExtractor
from urjakavach.cv_branch.geometry.learned_lsd import DeepLSDGeometryExtractor
from urjakavach.cv_branch.segmentation.sam3 import SAM3Segmentor
from urjakavach.schemas.canonical_schema import BBox, EngineeringEntity, ProvenanceSource

def test_dinov3_feature_shape():
    backbone = DINOv3Backbone(feature_dim=768, patch_size=14)
    dummy_img = np.zeros((140, 280, 3), dtype=np.uint8)
    feat = backbone.extract_dense_features(dummy_img)
    # 140/14 = 10, 280/14 = 20
    assert feat.shape == (10, 20, 768)

def test_symbol_detector_on_synthetic_pandid():
    # Create white canvas with a black circular instrument bubble and a valve
    img = np.ones((200, 200, 3), dtype=np.uint8) * 255
    # Circle at (50, 50), r=15
    cv2.circle(img, (50, 50), 15, (0, 0, 0), 2)
    # Triangle valve at (120, 100)
    pts1 = np.array([[100, 90], [120, 100], [100, 110]])
    pts2 = np.array([[140, 90], [120, 100], [140, 110]])
    cv2.drawContours(img, [pts1, pts2], -1, (0, 0, 0), -1)

    detector = EngineeringSymbolDetector(min_confidence=0.5)
    entities = detector.detect_symbols(img, image_path="test_synth.png")
    assert len(entities) > 0
    classes = [e.entity_class for e in entities]
    assert "instrument" in classes or "valve" in classes

def test_sam3_segmentation_refinement():
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    cv2.rectangle(img, (20, 20), (60, 60), (0, 0, 0), -1)

    segmentor = SAM3Segmentor()
    prov = ProvenanceSource(
        stage="cv_detector",
        model_name="test",
        image_path="test.png",
        global_coordinates=[15, 15, 65, 65]
    )
    ent = EngineeringEntity(
        id="ent_01",
        entity_class="vessel",
        bbox=BBox(x1=15, y1=15, x2=65, y2=65),
        confidence=0.9,
        source=prov
    )

    refined = segmentor.refine_entity(img, ent)
    assert refined.polygon is not None
    assert len(refined.polygon) > 0

def test_geometry_line_and_junction_extraction():
    img = np.ones((200, 200, 3), dtype=np.uint8) * 255
    # Horizontal line
    cv2.line(img, (20, 100), (180, 100), (0, 0, 0), 2)
    # Vertical line intersecting at (100, 100)
    cv2.line(img, (100, 20), (100, 180), (0, 0, 0), 2)

    extractor = OpenCVGeometryExtractor(min_line_length=20.0)
    lines = extractor.extract_lines(img, image_path="test.png")
    assert len(lines) >= 2
    
    junctions = extractor.find_junctions(lines)
    assert len(junctions) >= 1
    # Check intersection point near (100, 100)
    j_pt = junctions[0]["point"]
    assert abs(j_pt.x - 100) <= 5.0
    assert abs(j_pt.y - 100) <= 5.0

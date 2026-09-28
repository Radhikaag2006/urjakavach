"""
Unit tests for UrjaKavach Canonical and CAD Schemas.
"""

import pytest
from urjakavach.schemas.canonical_schema import (
    Point2D,
    BBox,
    ProvenanceSource,
    EngineeringEntity,
    LineSegmentObservation,
    TextObservation,
    CanonicalEngineeringDocument,
    DocumentMetadata,
    SCHEMA_VERSION,
)
from urjakavach.schemas.cad_schema import CADLine, CADDrawingVectorPackage

def test_bbox_properties():
    box = BBox(x1=10, y1=20, x2=50, y2=80)
    assert box.width == 40
    assert box.height == 60
    assert box.area == 2400
    assert box.center.x == 30.0
    assert box.center.y == 50.0
    assert box.to_list() == [10, 20, 50, 80]

def test_provenance_source():
    prov = ProvenanceSource(
        stage="cv_detector",
        model_name="TestDetector",
        image_path="test.png",
        page_number=1,
        global_coordinates=[10, 20, 30, 40]
    )
    assert prov.stage == "cv_detector"
    assert prov.model_name == "TestDetector"
    assert prov.global_coordinates == [10, 20, 30, 40]

def test_canonical_document_serialization():
    meta = DocumentMetadata(
        document_type="PID",
        title="Test P&ID",
        drawing_number="DWG-001",
        source_file="test.png",
        original_width=1000,
        original_height=800
    )
    box = BBox(x1=10, y1=10, x2=50, y2=50)
    prov = ProvenanceSource(
        stage="cv_detector",
        model_name="Detector",
        image_path="test.png",
        global_coordinates=[10, 10, 50, 50]
    )
    entity = EngineeringEntity(
        id="pump_001",
        entity_class="pump",
        label="P-101",
        bbox=box,
        confidence=0.95,
        source=prov
    )
    doc = CanonicalEngineeringDocument(
        schema_version=SCHEMA_VERSION,
        document_id="doc_test",
        metadata=meta,
        entities=[entity]
    )
    
    data = doc.to_json_dict()
    assert data["schema_version"] == "1.0.0"
    assert len(data["entities"]) == 1
    assert data["entities"][0]["label"] == "P-101"
    assert data["metadata"]["document_type"] == "PID"

def test_cad_schema():
    line = CADLine(
        handle="1A2B",
        layer="PIPES",
        start=(0.0, 0.0, 0.0),
        end=(100.0, 0.0, 0.0)
    )
    pkg = CADDrawingVectorPackage(
        filename="plant.dxf",
        lines=[line]
    )
    assert len(pkg.lines) == 1
    assert pkg.lines[0].layer == "PIPES"

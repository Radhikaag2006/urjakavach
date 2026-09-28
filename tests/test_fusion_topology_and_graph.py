"""
Unit tests for Topology, Fusion, Engineering Graph, and LLM Evidence Packaging.
"""

import pytest
from urjakavach.schemas.canonical_schema import (
    EngineeringEntity,
    LineSegmentObservation,
    TextObservation,
    BBox,
    Point2D,
    ProvenanceSource,
    DocumentMetadata,
    CanonicalEngineeringDocument,
)
from urjakavach.cv_branch.topology.reconstruction import TopologyReconstructor
from urjakavach.fusion.engine import FusionEngine
from urjakavach.graph.engineering_graph import EngineeringGraph
from urjakavach.llm_interface.prompt_builder import LLMEvidenceInterface

def test_topology_and_graph_queries():
    prov = ProvenanceSource(
        stage="test",
        model_name="test",
        image_path="test.png",
        global_coordinates=[0, 0, 10, 10]
    )

    # Equipment 1: Pump at (10, 50) to (40, 80)
    pump = EngineeringEntity(
        id="pump_001",
        entity_class="pump",
        label="P-101",
        bbox=BBox(x1=10, y1=50, x2=40, y2=80),
        confidence=0.9,
        source=prov
    )

    # Equipment 2: Tank at (150, 40) to (200, 100)
    tank = EngineeringEntity(
        id="tank_001",
        entity_class="tank",
        label="T-201",
        bbox=BBox(x1=150, y1=40, x2=200, y2=100),
        confidence=0.95,
        source=prov
    )

    # Pipe connecting Pump to Tank: start=(40, 65), end=(150, 65)
    pipe = LineSegmentObservation(
        id="pipe_101",
        start=Point2D(x=40.0, y=65.0),
        end=Point2D(x=150.0, y=65.0),
        length_px=110.0,
        angle_deg=0.0,
        is_orthogonal=True,
        line_type="pipe_primary",
        source=prov
    )

    # OCR tag adjacent to Pump
    tag = TextObservation(
        id="tag_01",
        text="P-101",
        bbox=BBox(x1=12, y1=82, x2=38, y2=95),
        confidence=0.98,
        block_type="label",
        source=prov
    )

    # Run Topology Reconstructor
    reconstructor = TopologyReconstructor(endpoint_proximity_px=10.0, label_proximity_px=30.0)
    relationships = reconstructor.build_topology(
        entities=[pump, tank],
        lines=[pipe],
        text_blocks=[tag]
    )

    assert len(relationships) >= 3
    rel_types = [r.relation_type for r in relationships]
    assert "TERMINATES_AT" in rel_types
    assert "CONNECTED_TO" in rel_types
    assert "HAS_LABEL" in rel_types

    # Run Fusion Engine
    fusion = FusionEngine()
    paddle_data = {
        "text_observations": [tag],
        "table_observations": [],
        "layout_boxes": []
    }
    canonical_doc = fusion.fuse(
        document_id="doc_demo",
        image_path="test.png",
        image_width=500,
        image_height=300,
        paddle_data=paddle_data,
        entities=[pump, tank],
        lines=[pipe],
        relationships=relationships
    )

    assert len(canonical_doc.entities) == 2
    assert len(canonical_doc.relationships) >= 3

    # Load into Engineering Graph
    graph = EngineeringGraph(canonical_doc)
    
    # Query: What is connected to P-101?
    conns = graph.query_connected_entities("P-101")
    assert len(conns) > 0
    connected_labels = [c["connected_label"] for c in conns]
    assert "T-201" in connected_labels or "pipe_101" in [c["connected_id"] for c in conns]

    # Test LLM Evidence Interface
    llm_iface = LLMEvidenceInterface(graph)
    ans = llm_iface.answer_query_from_graph("What is connected to P-101?")
    assert ans["status"] == "SUCCESS"
    assert ans["evidence_grounded"] is True

    # Test Insufficient Evidence fallback
    unk_ans = llm_iface.answer_query_from_graph("What is connected to Heat Exchanger HX-999?")
    assert unk_ans["status"] == "INSUFFICIENT_EVIDENCE"
    assert unk_ans["evidence_grounded"] is False
    assert "No topological line connectivity was established" in unk_ans["reason"]

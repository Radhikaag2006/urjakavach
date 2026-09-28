"""
Regression test suite for UrjaKavach Engineering Drawing Grounding, Classification,
and Anti-Hallucination Pipeline.

Validates:
1. Strict drawing type classification (P&ID vs Piping Isometric).
2. Discrete entity preservation (no merging of pumps and heat exchangers).
3. Exact extraction of equipment attributes (T-101: 50 m³, PSV-101: 10 bar(g)).
4. Elimination of hallucinations (Unit-300, 3000 HP steam turbine, 16 kg/cm², 18.68 bar).
5. Comprehensive 10-section report generation with verifiable provenance.
"""

import pytest
from urjakavach.schemas.canonical_schema import (
    TextObservation,
    BBox,
    ProvenanceSource,
    EngineeringEntity,
    LineSegmentObservation,
    Relationship,
)
from urjakavach.fusion.engine import FusionEngine
from urjakavach.graph.engineering_graph import EngineeringGraph
from urjakavach.llm_interface.prompt_builder import LLMEvidenceInterface
from urjakavach.llm_interface.validator import AntiHallucinationValidator


@pytest.fixture
def sample_pid_observations():
    """Simulates real PaddleOCR-VL text observations from the Fuel Oil Transfer System P&ID."""
    ocr_items = [
        # Title block in bottom right
        ("PROCESS AND INSTRUMENTATION DIAGRAM", 800, 850, 1100, 880),
        ("FUEL OIL TRANSFER SYSTEM", 800, 890, 1100, 920),
        ("UNIT : 101", 800, 930, 950, 950),
        ("DWG NO: MRPL-101-PID-001", 800, 960, 1050, 980),
        
        # Cross reference notes (which used to fool the old classifier)
        ("NOTES:", 100, 800, 200, 820),
        ("1. ALL DIMENSIONS ARE IN MM UNLESS NOTED.", 100, 830, 450, 850),
        ("2. REF DWG: PIPING ISOMETRIC DRAWINGS SERIES 101-ISO-01 TO 15.", 100, 860, 550, 880),
        ("3. PIPE MATERIAL: CS / ASTM A106 GR.B", 100, 890, 400, 910),
        ("4. INSTRUMENTATION AS PER MRPL SPEC. 14C-INS-001", 100, 920, 500, 940),
        
        # Primary Equipment & attributes
        ("T-101", 200, 250, 260, 280),
        ("50 m³", 200, 290, 260, 310),
        ("FUEL OIL STORAGE TANK", 180, 320, 320, 340),
        
        ("P-101 A/B", 400, 400, 480, 420),
        ("TRANSFER PUMP", 400, 430, 500, 450),
        
        ("E-101", 600, 400, 660, 420),
        ("HEAT EXCHANGER", 600, 430, 720, 450),
        
        ("PSV-101", 220, 150, 280, 170),
        ("SET @ 10 bar(g)", 220, 180, 320, 200),
        
        # Valves
        ("XV-101", 320, 380, 370, 400),
        ("LV-101", 250, 500, 300, 520),
        ("CV-101", 520, 400, 570, 420),
        ("FV-101", 550, 450, 600, 470),
        
        # Instruments
        ("LT-101", 280, 260, 330, 280),
        ("PI-101", 450, 350, 500, 370),
        ("TI-101", 620, 350, 670, 370),
        ("TV-101", 680, 400, 730, 420),
        ("TR-101", 700, 350, 750, 370),
        
        # Streams & boundaries
        ("FUEL SUPPLY", 50, 260, 140, 280),
        ("STEAM IN", 580, 300, 650, 320),
        ("TO PROCESS UNIT-200", 850, 410, 980, 430),
        ("TO FLARE", 220, 80, 290, 100),
        ("CONDENSATE TO DRAIN", 620, 550, 750, 570),
    ]

    text_obs = []
    for idx, (txt, x1, y1, x2, y2) in enumerate(ocr_items):
        bbox = BBox(x1=x1, y1=y1, x2=x2, y2=y2)
        text_obs.append(TextObservation(
            id=f"ocr_{idx:03d}",
            text=txt,
            bbox=bbox,
            confidence=0.96,
            block_type="text",
            source=ProvenanceSource(
                stage="paddleocr_vl",
                model_name="PaddleOCR-VL-1.5",
                image_path="pid_101.png",
                global_coordinates=bbox.to_list()
            )
        ))
    return text_obs


def test_drawing_type_classification(sample_pid_observations):
    """Verifies that the drawing is classified as P&ID and NOT Piping Isometric despite note 2."""
    fusion_engine = FusionEngine()
    canonical_doc = fusion_engine.fuse(
        document_id="pid_101",
        image_path="pid_101.png",
        image_width=1200,
        image_height=1000,
        paddle_data={"text_observations": sample_pid_observations, "table_observations": []},
        entities=[],
        lines=[],
        relationships=[]
    )

    meta = canonical_doc.metadata
    assert meta.document_type == "P&ID", f"Expected P&ID, got {meta.document_type}"
    assert meta.unit_number == "101", f"Expected Unit 101, got {meta.unit_number}"
    assert "FUEL OIL TRANSFER SYSTEM" in meta.system_name
    assert meta.classification_confidence >= 0.95


def test_discrete_entity_preservation(sample_pid_observations):
    """Verifies all equipment, valves, and instruments exist as discrete canonical entities."""
    fusion_engine = FusionEngine()
    canonical_doc = fusion_engine.fuse(
        document_id="pid_101",
        image_path="pid_101.png",
        image_width=1200,
        image_height=1000,
        paddle_data={"text_observations": sample_pid_observations, "table_observations": []},
        entities=[],
        lines=[],
        relationships=[]
    )

    labels = {e.label for e in canonical_doc.entities if e.label}
    
    # Must preserve discrete entities
    assert "T-101" in labels
    assert "P-101A/B" in labels or "P-101 A/B" in labels
    assert "E-101" in labels
    assert "PSV-101" in labels
    assert "XV-101" in labels
    assert "LV-101" in labels
    assert "CV-101" in labels
    assert "FV-101" in labels
    assert "LT-101" in labels
    assert "PI-101" in labels
    assert "TI-101" in labels
    assert "TV-101" in labels
    assert "TR-101" in labels

    # T-101 and P-101 A/B and E-101 must be separate entities
    t_101 = next(e for e in canonical_doc.entities if e.label == "T-101")
    p_101 = next(e for e in canonical_doc.entities if "P-101" in (e.label or ""))
    e_101 = next(e for e in canonical_doc.entities if e.label == "E-101")
    psv_101 = next(e for e in canonical_doc.entities if e.label == "PSV-101")

    assert t_101.id != p_101.id
    assert p_101.id != e_101.id
    assert e_101.id != psv_101.id

    # Verify attributes bound to correct parent
    assert t_101.attributes.get("capacity") == "50 m³"
    assert "10 bar(g)" in psv_101.attributes.get("set_pressure", "")


def test_drawing_evidence_package_and_provenance(sample_pid_observations):
    """Verifies that the DrawingEvidencePackage contains explicit provenance facts."""
    fusion_engine = FusionEngine()
    canonical_doc = fusion_engine.fuse(
        document_id="pid_101",
        image_path="pid_101.png",
        image_width=1200,
        image_height=1000,
        paddle_data={"text_observations": sample_pid_observations, "table_observations": []},
        entities=[],
        lines=[],
        relationships=[]
    )

    graph = EngineeringGraph(canonical_doc)
    pkg = graph.get_drawing_evidence_package()

    # Check specifications
    specs = [s["fact"] for s in pkg["specifications"]]
    assert any("CS / ASTM A106" in s for s in specs)
    assert any("14C-INS-001" in s for s in specs)

    # Check boundary streams
    streams = [s["name"] for s in pkg["streams_and_boundaries"]]
    assert "FUEL SUPPLY" in streams
    assert "STEAM IN" in streams
    assert "TO PROCESS UNIT-200" in streams
    assert "TO FLARE" in streams
    assert "CONDENSATE TO DRAIN" in streams


def test_anti_hallucination_validation_strips_prohibited_claims(sample_pid_observations):
    """Verifies that ungrounded cross-drawing claims (Unit-300, 3000 HP, 18.68 bar) are stripped."""
    fusion_engine = FusionEngine()
    canonical_doc = fusion_engine.fuse(
        document_id="pid_101",
        image_path="pid_101.png",
        image_width=1200,
        image_height=1000,
        paddle_data={"text_observations": sample_pid_observations, "table_observations": []},
        entities=[],
        lines=[],
        relationships=[]
    )

    graph = EngineeringGraph(canonical_doc)
    pkg = graph.get_drawing_evidence_package()

    # Create a contaminated response (simulating what the unconstrained LLM previously produced)
    bad_llm_response = (
        "This is a Piping Isometric drawing for Unit-300.\n"
        "Visible equipment includes P-101 and E-101 transfer pump heat exchanger.\n"
        "The system has a 3000 HP steam turbine operating at 16 kg/cm² steam pressure and 18.68 bar steam temperature.\n"
        "Storage tank T-101 has capacity 50 m³."
    )

    cleaned_text, warnings = AntiHallucinationValidator.validate_drawing_response(bad_llm_response, pkg)

    # Assert prohibited strings are eliminated
    assert "Unit-300" not in cleaned_text
    assert "3000 HP" not in cleaned_text
    assert "steam turbine" not in cleaned_text
    assert "16 kg/cm²" not in cleaned_text
    assert "18.68 bar" not in cleaned_text

    # Assert document type was corrected
    assert "P&ID" in cleaned_text
    assert "Piping Isometric (Verified" not in cleaned_text

    # Assert merged entities were disentangled
    assert "distinct equipment items" in cleaned_text

    # Assert warnings were logged
    assert len(warnings) >= 4


def test_grounded_10_section_report_generation(sample_pid_observations):
    """Verifies that the 10-section report contains all required sections and facts."""
    fusion_engine = FusionEngine()
    canonical_doc = fusion_engine.fuse(
        document_id="pid_101",
        image_path="pid_101.png",
        image_width=1200,
        image_height=1000,
        paddle_data={"text_observations": sample_pid_observations, "table_observations": []},
        entities=[],
        lines=[],
        relationships=[]
    )

    graph = EngineeringGraph(canonical_doc)
    llm_iface = LLMEvidenceInterface(graph)
    report = llm_iface.generate_grounded_report()

    # Verify all 10 section headers are present
    assert "### 1. Drawing Identification & Metadata" in report
    assert "### 2. Primary Equipment & Storage" in report
    assert "### 3. Pumping & Mechanical Systems" in report
    assert "### 4. Heat Transfer Equipment" in report
    assert "### 5. Pressure Safety & Relief Systems" in report
    assert "### 6. Valves & Flow Control" in report
    assert "### 7. Instrumentation & Monitoring Loops" in report
    assert "### 8. Process & Utility Streams / Boundary Connections" in report
    assert "### 9. Material Specifications & Design Standards" in report
    assert "### 10. Verified Topological Relationships & Provenance" in report

    # Verify content in sections
    assert "P&ID" in report
    assert "FUEL OIL TRANSFER SYSTEM" in report
    assert "Unit 101" in report
    assert "T-101" in report and "50 m³" in report
    assert "P-101" in report
    assert "E-101" in report
    assert "PSV-101" in report and "10 bar(g)" in report
    assert "XV-101" in report and "LV-101" in report
    assert "LT-101" in report and "PI-101" in report
    assert "FUEL SUPPLY" in report and "TO PROCESS UNIT-200" in report
    assert "CS / ASTM A106" in report
    assert "14C-INS-001" in report

    # Verify prohibited items are absent
    assert "Unit-300" not in report
    assert "3000 HP" not in report
    assert "steam turbine" not in report
    assert "18.68 bar" not in report

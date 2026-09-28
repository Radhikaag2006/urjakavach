"""
UrjaKavach Canonical Engineering Document Schema (v1.0.0).
Provides formal, strongly-typed Pydantic definitions for all engineering drawing
observations, entities, geometric primitives, topological relationships, and provenance.
"""

from typing import List, Dict, Any, Optional, Tuple, Literal
from pydantic import BaseModel, Field, ConfigDict
import time

SCHEMA_VERSION: str = "1.0.0"

class Point2D(BaseModel):
    x: float
    y: float

class BBox(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return max(0, self.x2 - self.x1)

    @property
    def height(self) -> int:
        return max(0, self.y2 - self.y1)

    @property
    def center(self) -> Point2D:
        return Point2D(x=(self.x1 + self.x2) / 2.0, y=(self.y1 + self.y2) / 2.0)

    @property
    def area(self) -> int:
        return self.width * self.height

    def to_list(self) -> List[int]:
        return [self.x1, self.y1, self.x2, self.y2]

class ProvenanceSource(BaseModel):
    """Traces every extracted element back to its source detector, OCR model, and coordinates."""
    model_config = ConfigDict(extra="allow")
    
    stage: str = Field(..., description="Pipeline stage: 'paddleocr_vl', 'cv_detector', 'geometry', 'fusion'")
    model_name: str = Field(..., description="Exact model/algorithm name (e.g. 'PaddleOCR-VL-1.5', 'DINOv3-Large', 'DeepLSD', 'OpenCV-LSD')")
    image_path: str = Field(default="", description="Relative or absolute path to source drawing image")
    page_number: int = Field(default=1, description="Page number for multi-page documents")
    tile_id: Optional[str] = Field(default=None, description="Tile ID if high-resolution tiling was applied")
    local_coordinates: Optional[List[int]] = Field(default=None, description="Coordinates in local tile if tiled")
    global_coordinates: List[int] = Field(default_factory=list, description="Canonical [x1, y1, x2, y2] in original full-resolution image")
    timestamp: float = Field(default_factory=time.time)

class TextObservation(BaseModel):
    """Text observed by PaddleOCR-VL or fine-grained OCR."""
    id: str
    text: str
    bbox: BBox
    polygon: Optional[List[List[int]]] = None
    confidence: float = Field(ge=0.0, le=1.0)
    block_type: str = Field(default="text", description="title, note, callout, dimension, table_cell, label, figure_title")
    source: ProvenanceSource

class TableObservation(BaseModel):
    """Structured table recognized by PaddleOCR-VL."""
    id: str
    table_html: str
    bbox: BBox
    num_rows: Optional[int] = None
    num_cols: Optional[int] = None
    headers: List[str] = Field(default_factory=list)
    source: ProvenanceSource

class LineSegmentObservation(BaseModel):
    """2D line segment or long pipe run extracted by geometry engines."""
    id: str
    start: Point2D
    end: Point2D
    length_px: float
    angle_deg: float
    thickness_px: float = 1.0
    line_type: Literal[
        "pipe_primary", "pipe_secondary", "instrument_signal",
        "electrical_wire", "dimension_line", "centerline", "border", "unknown"
    ] = "unknown"
    is_orthogonal: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: ProvenanceSource

class EngineeringEntity(BaseModel):
    """Detected engineering component or symbol (e.g. pump, valve, vessel)."""
    id: str
    entity_class: str = Field(..., description="valve, pump, compressor, vessel, tank, heat_exchanger, instrument, flange, etc.")
    label: Optional[str] = Field(default=None, description="Tag or identifier (e.g. 'P-101', 'V-204')")
    bbox: BBox
    polygon: Optional[List[List[int]]] = None
    mask_rle: Optional[str] = Field(default=None, description="Compressed RLE mask from SAM")
    confidence: float = Field(ge=0.0, le=1.0)
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Domain attributes (e.g. 'valve_type': 'gate', 'diameter': '4in')")
    source: ProvenanceSource

class EvidenceFact(BaseModel):
    """Drawing-scoped explicit evidence fact with strict provenance."""
    fact: str
    source: Literal["ocr", "cv", "geometry", "fusion"]
    confidence: float = Field(ge=0.0, le=1.0)
    source_region: List[int] = Field(default_factory=list)
    evidence_text: str = ""
    status: Literal["OBSERVATION", "INFERENCE", "ENGINEERING_FACT"] = "OBSERVATION"
    target_entity_id: Optional[str] = None

class DimensionObservation(BaseModel):
    """Engineering dimension annotation linking numerical value with geometric leader."""
    id: str
    value: str
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    tolerance: Optional[str] = None
    target_feature_id: Optional[str] = None
    leader_line_coords: Optional[List[List[int]]] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: ProvenanceSource

class Relationship(BaseModel):
    """Topological or semantic relationship connecting two engineering entities or primitives."""
    id: str
    source_id: str
    relation_type: Literal[
        "CONNECTED_TO",
        "CONTAINS",
        "LOCATED_NEAR",
        "HAS_LABEL",
        "HAS_DIMENSION",
        "HAS_SPECIFICATION",
        "PART_OF",
        "FLOWS_TO",
        "CONNECTS_TO",
        "TERMINATES_AT",
        "INTERSECTS"
    ]
    target_id: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    status: Literal["OBSERVATION", "INFERENCE", "ENGINEERING_FACT"] = "OBSERVATION"
    evidence: Dict[str, Any] = Field(
        default_factory=dict,
        description="Physical/geometric evidence (e.g. intersection point, shared endpoint distance, leader line path)"
    )

CONTROLLED_DOCUMENT_TYPES = [
    "P&ID",
    "Piping Isometric",
    "General Arrangement",
    "Plot Plan / Site Layout",
    "Piping Layout",
    "Equipment Layout",
    "Pipe Support Detail",
    "Instrumentation Layout",
    "Foundation Drawing",
    "Revision / Title Block",
    "Unknown",
]

class DocumentMetadata(BaseModel):
    document_type: str = Field(default="Unknown", description="Controlled drawing type e.g. P&ID, Piping Isometric, General Arrangement...")
    drawing_number: Optional[str] = None
    title: Optional[str] = None
    unit_number: Optional[str] = None
    project_name: Optional[str] = None
    system_name: Optional[str] = None
    revision: Optional[str] = None
    sheet_number: Optional[str] = None
    total_sheets: Optional[str] = None
    scale: Optional[str] = None
    units: Optional[str] = None
    drafter: Optional[str] = None
    approver: Optional[str] = None
    source_file: str
    original_width: int
    original_height: int
    classification_confidence: float = 1.0
    classification_evidence: Optional[Dict[str, Any]] = None

class DrawingEvidencePackage(BaseModel):
    """Self-contained, drawing-isolated evidence package passed to the local LLM."""
    document_id: str
    metadata: DocumentMetadata
    regional_ocr_text: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    detected_entities: List[Dict[str, Any]] = Field(default_factory=list)
    detected_symbols: List[Dict[str, Any]] = Field(default_factory=list)
    instrument_tags: List[Dict[str, Any]] = Field(default_factory=list)
    dimensions: List[Dict[str, Any]] = Field(default_factory=list)
    specifications: List[Dict[str, Any]] = Field(default_factory=list)
    line_geometry: List[Dict[str, Any]] = Field(default_factory=list)
    topology_observations: List[Dict[str, Any]] = Field(default_factory=list)
    topology_inferences: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_facts: List[EvidenceFact] = Field(default_factory=list)
    notes_and_standards: List[str] = Field(default_factory=list)

class CanonicalEngineeringDocument(BaseModel):
    """Root canonical representation of an engineering document."""
    schema_version: str = SCHEMA_VERSION
    document_id: str
    metadata: DocumentMetadata
    layout_regions: List[Dict[str, Any]] = Field(default_factory=list, description="Macro-layout regions from PaddleOCR-VL")
    entities: List[EngineeringEntity] = Field(default_factory=list)
    lines: List[LineSegmentObservation] = Field(default_factory=list)
    text_blocks: List[TextObservation] = Field(default_factory=list)
    tables: List[TableObservation] = Field(default_factory=list)
    dimensions: List[DimensionObservation] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)
    evidence_facts: List[EvidenceFact] = Field(default_factory=list)

    def to_json_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

"""
UrjaKavach Computer Vision & Engineering Drawing Subsystem.
Modular document understanding, fine-grained symbol detection, geometry extraction,
multi-modal fusion, and graph synthesis for engineering drawings.
"""

from urjakavach.pipeline import UrjaKavachPipeline
from urjakavach.schemas.canonical_schema import (
    CanonicalEngineeringDocument,
    EngineeringEntity,
    LineSegmentObservation,
    TextObservation,
    TableObservation,
    DimensionObservation,
    Relationship,
    SCHEMA_VERSION,
)
from urjakavach.graph.engineering_graph import EngineeringGraph
from urjakavach.llm_interface.prompt_builder import LLMEvidenceInterface

__all__ = [
    "UrjaKavachPipeline",
    "CanonicalEngineeringDocument",
    "EngineeringEntity",
    "LineSegmentObservation",
    "TextObservation",
    "TableObservation",
    "DimensionObservation",
    "Relationship",
    "SCHEMA_VERSION",
    "EngineeringGraph",
    "LLMEvidenceInterface",
]

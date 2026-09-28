"""
Multi-Task Engineering Drawing Dataset Management.
Provides separate annotation categories for:
1. Text
2. Engineering objects
3. Symbols
4. Lines/Pipes
5. Dimensions
6. Geometric primitives
7. Relationships/Topology
Supports expansion beyond smoke-test datasets for multi-task model training & evaluation.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import json
from pathlib import Path

class TextAnnotation(BaseModel):
    id: str
    text: str
    bbox: List[int]
    polygon: Optional[List[List[int]]] = None
    block_type: str = "text"

class SymbolAnnotation(BaseModel):
    id: str
    category: str
    tag: Optional[str] = None
    bbox: List[int]
    polygon: Optional[List[List[int]]] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)

class PipeLineAnnotation(BaseModel):
    id: str
    polyline: List[List[float]]
    line_type: str = "pipe_primary"
    is_orthogonal: bool = True

class DimensionAnnotation(BaseModel):
    id: str
    value: str
    leader_line: Optional[List[List[float]]] = None
    target_id: Optional[str] = None

class TopologyAnnotation(BaseModel):
    id: str
    source_id: str
    relation: str
    target_id: str
    evidence: Dict[str, Any] = Field(default_factory=dict)

class DrawingAnnotationRecord(BaseModel):
    """Complete multi-task ground truth record for a single engineering drawing."""
    drawing_id: str
    image_filename: str
    width: int
    height: int
    document_type: str
    texts: List[TextAnnotation] = Field(default_factory=list)
    symbols: List[SymbolAnnotation] = Field(default_factory=list)
    lines: List[PipeLineAnnotation] = Field(default_factory=list)
    dimensions: List[DimensionAnnotation] = Field(default_factory=list)
    topology: List[TopologyAnnotation] = Field(default_factory=list)

class MultiTaskEngineeringDataset:
    """Manages multi-task annotated datasets for training and benchmarking."""

    def __init__(self, dataset_name: str = "UrjaKavach-Benchmark-v1"):
        self.dataset_name = dataset_name
        self.records: Dict[str, DrawingAnnotationRecord] = {}

    def add_record(self, record: DrawingAnnotationRecord):
        self.records[record.drawing_id] = record

    def save_dataset(self, out_path: str):
        data = {
            "dataset_name": self.dataset_name,
            "count": len(self.records),
            "records": [r.model_dump() for r in self.records.values()]
        }
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load_dataset(cls, in_path: str) -> "MultiTaskEngineeringDataset":
        with open(in_path, "r") as f:
            data = json.load(f)
        ds = cls(dataset_name=data.get("dataset_name", "LoadedDataset"))
        for rec in data.get("records", []):
            ds.add_record(DrawingAnnotationRecord(**rec))
        return ds

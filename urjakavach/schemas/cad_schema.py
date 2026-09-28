"""
UrjaKavach Native CAD / Vector Schema.
Allows CAD files (DXF, DWG, SVG) to bypass raster perception and feed high-fidelity
geometric primitives directly into the Fusion and Topology layers.
"""

from typing import List, Dict, Any, Optional, Tuple, Literal
from pydantic import BaseModel, Field

class CADLayer(BaseModel):
    name: str
    color: Optional[str] = None
    linetype: Optional[str] = None
    is_visible: bool = True

class CADLine(BaseModel):
    entity_type: Literal["LINE"] = "LINE"
    handle: str
    layer: str
    start: Tuple[float, float, float]
    end: Tuple[float, float, float]
    thickness: float = 1.0

class CADArc(BaseModel):
    entity_type: Literal["ARC"] = "ARC"
    handle: str
    layer: str
    center: Tuple[float, float, float]
    radius: float
    start_angle_deg: float
    end_angle_deg: float

class CADPolyline(BaseModel):
    entity_type: Literal["POLYLINE"] = "POLYLINE"
    handle: str
    layer: str
    vertices: List[Tuple[float, float, float]]
    is_closed: bool = False

class CADText(BaseModel):
    entity_type: Literal["TEXT", "MTEXT"] = "TEXT"
    handle: str
    layer: str
    text_content: str
    insertion_point: Tuple[float, float, float]
    height: float
    rotation_deg: float = 0.0

class CADDimension(BaseModel):
    entity_type: Literal["DIMENSION"] = "DIMENSION"
    handle: str
    layer: str
    text: str
    defpoint: Tuple[float, float, float]
    text_midpoint: Tuple[float, float, float]

class CADBlockReference(BaseModel):
    entity_type: Literal["BLOCK"] = "BLOCK"
    handle: str
    block_name: str
    layer: str
    insertion_point: Tuple[float, float, float]
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    rotation_deg: float = 0.0
    attributes: Dict[str, str] = Field(default_factory=dict)

class CADDrawingVectorPackage(BaseModel):
    """Complete vector representation parsed from DXF/DWG files."""
    filename: str
    layers: List[CADLayer] = Field(default_factory=list)
    lines: List[CADLine] = Field(default_factory=list)
    arcs: List[CADArc] = Field(default_factory=list)
    polylines: List[CADPolyline] = Field(default_factory=list)
    texts: List[CADText] = Field(default_factory=list)
    dimensions: List[CADDimension] = Field(default_factory=list)
    blocks: List[CADBlockReference] = Field(default_factory=list)

"""
UrjaKavach Multi-Modal Fusion Engine.
Fuses PaddleOCR-VL document observations with Computer Vision symbols,
segmentation masks, geometric line networks, and topology into a unified
Canonical Engineering Document with complete provenance.
"""

from typing import List, Dict, Any, Optional
import re
import math
from pathlib import Path
from urjakavach.schemas.canonical_schema import (
    CanonicalEngineeringDocument,
    DocumentMetadata,
    EngineeringEntity,
    LineSegmentObservation,
    TextObservation,
    TableObservation,
    DimensionObservation,
    Relationship,
    BBox,
    Point2D,
    ProvenanceSource,
    SCHEMA_VERSION,
)

class FusionEngine:
    """Fuses multi-modal perceptual streams into canonical engineering truth."""

    def __init__(self, document_type_hint: Optional[str] = None):
        self.document_type_hint = document_type_hint

    def fuse(
        self,
        document_id: str,
        image_path: str,
        image_width: int,
        image_height: int,
        paddle_data: Dict[str, Any],
        entities: List[EngineeringEntity],
        lines: List[LineSegmentObservation],
        relationships: List[Relationship]
    ) -> CanonicalEngineeringDocument:
        """
        Executes multi-modal fusion.
        """
        text_blocks: List[TextObservation] = paddle_data.get("text_observations", [])
        tables: List[TableObservation] = paddle_data.get("table_observations", [])
        layout_boxes: List[Dict[str, Any]] = paddle_data.get("layout_boxes", [])

        # 1. Infer Document Metadata from Title Blocks, Captions, and Tables
        metadata = self._extract_metadata(
            image_path=image_path,
            width=image_width,
            height=image_height,
            text_blocks=text_blocks,
            tables=tables,
            layout_boxes=layout_boxes
        )

        # 2. Extract Dimensions from text blocks and geometry
        dimensions = self._extract_dimensions(text_blocks, lines, image_path)

        # 3. Fuse Entity Labels & Provenance
        fused_entities = self._fuse_entity_labels(entities, text_blocks)

        # 4. Integrate Cross-Modal Topological Edges
        # Augment entities with connected line IDs and partner entities
        for rel in relationships:
            if rel.relation_type == "CONNECTED_TO":
                src = next((e for e in fused_entities if e.id == rel.source_id), None)
                tgt = next((e for e in fused_entities if e.id == rel.target_id), None)
                if src and tgt:
                    src.attributes.setdefault("connected_to", []).append(tgt.id)
                    tgt.attributes.setdefault("connected_to", []).append(src.id)
            elif rel.relation_type == "TERMINATES_AT":
                line_obj = next((l for l in lines if l.id == rel.source_id), None)
                ent_obj = next((e for e in fused_entities if e.id == rel.target_id), None)
                if line_obj and ent_obj:
                    ent_obj.attributes.setdefault("connected_lines", []).append(line_obj.id)

        canonical_doc = CanonicalEngineeringDocument(
            schema_version=SCHEMA_VERSION,
            document_id=document_id,
            metadata=metadata,
            layout_regions=layout_boxes,
            entities=fused_entities,
            lines=lines,
            text_blocks=text_blocks,
            tables=tables,
            dimensions=dimensions,
            relationships=relationships
        )

        return canonical_doc

    def _extract_metadata(
        self,
        image_path: str,
        width: int,
        height: int,
        text_blocks: List[TextObservation],
        tables: List[TableObservation],
        layout_boxes: List[Dict[str, Any]]
    ) -> DocumentMetadata:
        """Heuristically extracts drawing title, number, and type from OCR and layout evidence."""
        title = None
        drawing_no = None
        doc_type = self.document_type_hint or "UNKNOWN"

        # Search for figure titles or headers
        for tb in text_blocks:
            txt = tb.text.strip()
            # Title patterns
            if tb.block_type in ("figure_title", "title") or re.search(r"^(figure|fig\.|table|dwg|drawing)\s+[\d\.\-]+", txt, re.IGNORECASE):
                if title is None or len(txt) > len(title):
                    title = txt
                # Extract number e.g. Figure 11.2-3
                m_num = re.search(r"(?:figure|fig\.|table|dwg)\s*([0-9A-Z\.\-]+)", txt, re.IGNORECASE)
                if m_num and not drawing_no:
                    drawing_no = m_num.group(1)

        # Detect document type from textual cues
        combined_text = " ".join(t.text for t in text_blocks).lower()
        if "process flow" in combined_text or "flow diagram" in combined_text:
            doc_type = "PFD"
        elif "piping & instrumentation" in combined_text or "p&id" in combined_text:
            doc_type = "PID"
        elif "schematic" in combined_text or "wiring" in combined_text or "circuit" in combined_text:
            doc_type = "ELECTRICAL_SCHEMATIC"
        elif "emission factors" in combined_text or len(tables) > 0 and len(text_blocks) < 5:
            doc_type = "SPECIFICATION_SHEET"

        return DocumentMetadata(
            document_type=doc_type,
            drawing_number=drawing_no,
            title=title or Path(image_path).stem,
            revision=None,
            source_file=image_path,
            original_width=width,
            original_height=height
        )

    def _extract_dimensions(
        self,
        text_blocks: List[TextObservation],
        lines: List[LineSegmentObservation],
        image_path: str
    ) -> List[DimensionObservation]:
        """Identifies dimensional annotations with numerical values and units."""
        dim_regex = re.compile(r"^\s*([ØøR]?\s*\d+(?:\.\d+)?)\s*(mm|m|cm|in|\"|'|ft|°|deg|kpa|bar|psi)?\s*$", re.IGNORECASE)
        dimensions: List[DimensionObservation] = []
        counter = 0

        for tb in text_blocks:
            m = dim_regex.match(tb.text.strip())
            if m:
                val_str = m.group(1).strip()
                unit_str = m.group(2) if m.group(2) else None
                try:
                    num_val = float(re.sub(r"[^\d\.]", "", val_str))
                except ValueError:
                    num_val = None

                counter += 1
                dimensions.append(DimensionObservation(
                    id=f"dim_{counter:04d}",
                    value=tb.text.strip(),
                    numeric_value=num_val,
                    unit=unit_str,
                    confidence=0.90,
                    source=ProvenanceSource(
                        stage="fusion",
                        model_name="DimensionExtractor",
                        image_path=image_path,
                        global_coordinates=tb.bbox.to_list()
                    )
                ))
        return dimensions

    def _fuse_entity_labels(
        self,
        entities: List[EngineeringEntity],
        text_blocks: List[TextObservation]
    ) -> List[EngineeringEntity]:
        """Binds alphanumeric tag labels to detected engineering symbols."""
        for ent in entities:
            if ent.label:
                continue

            ec = ent.bbox.center
            best_label = None
            min_dist = float("inf")

            for tb in text_blocks:
                txt = tb.text.strip()
                if len(txt) > 30:
                    continue

                tc = tb.bbox.center
                dist = math.hypot(tc.x - ec.x, tc.y - ec.y)
                
                # Tag within proximity
                if dist < 45.0 and dist < min_dist:
                    min_dist = dist
                    best_label = txt

            if best_label:
                ent.label = best_label
                ent.attributes["label_binding_distance_px"] = round(min_dist, 2)

        return entities

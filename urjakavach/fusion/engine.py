"""
UrjaKavach Multi-Modal Fusion Engine.
Fuses PaddleOCR-VL document observations with Computer Vision symbols,
segmentation masks, geometric line networks, and topology into a unified
Canonical Engineering Document with complete provenance.
"""

from typing import List, Dict, Any, Optional, Tuple
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
    EvidenceFact,
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
        Executes multi-modal fusion with drawing-scoped evidence tracking.
        """
        text_blocks: List[TextObservation] = paddle_data.get("text_observations", [])
        tables: List[TableObservation] = paddle_data.get("table_observations", [])
        layout_boxes: List[Dict[str, Any]] = paddle_data.get("layout_boxes", [])

        # 1. Infer Document Metadata from Title Blocks, Captions, and Tables
        metadata, metadata_facts = self._extract_metadata(
            image_path=image_path,
            width=image_width,
            height=image_height,
            text_blocks=text_blocks,
            tables=tables,
            layout_boxes=layout_boxes
        )

        # 2. Extract Dimensions from text blocks and geometry
        dimensions, dim_facts = self._extract_dimensions(text_blocks, lines, image_path)

        # 3. Fuse Entity Labels, Attributes & Provenance
        fused_entities, entity_facts = self._fuse_entity_labels(entities, text_blocks, image_path)

        # 4. Integrate Cross-Modal Topological Edges & Facts
        topo_facts = []
        for rel in relationships:
            src_ent = next((e for e in fused_entities if e.id == rel.source_id), None)
            tgt_ent = next((e for e in fused_entities if e.id == rel.target_id), None)
            
            if rel.relation_type == "CONNECTED_TO":
                if src_ent and tgt_ent:
                    src_ent.attributes.setdefault("connected_to", []).append(tgt_ent.id)
                    tgt_ent.attributes.setdefault("connected_to", []).append(src_ent.id)
                    s_label = src_ent.label or src_ent.id
                    t_label = tgt_ent.label or tgt_ent.id
                    topo_facts.append(EvidenceFact(
                        fact=f"{s_label} is connected to {t_label}",
                        source="geometry",
                        confidence=rel.confidence,
                        source_region=src_ent.bbox.to_list(),
                        evidence_text=f"Line link via {rel.evidence.get('via_line_id', 'pipe')}",
                        status=rel.status,
                        target_entity_id=src_ent.id
                    ))
            elif rel.relation_type == "TERMINATES_AT":
                line_obj = next((l for l in lines if l.id == rel.source_id), None)
                if line_obj and tgt_ent:
                    tgt_ent.attributes.setdefault("connected_lines", []).append(line_obj.id)

        all_evidence_facts = metadata_facts + entity_facts + dim_facts + topo_facts

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
            relationships=relationships,
            evidence_facts=all_evidence_facts,
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
    ) -> Tuple[DocumentMetadata, List[EvidenceFact]]:
        """Extracts drawing title, number, unit, and controlled document type strictly from title block evidence."""
        title = None
        drawing_no = None
        unit_no = None
        project_name = None
        system_name = None
        doc_type = self.document_type_hint or "Unknown"
        conf = 0.5
        evidence_info = {}
        metadata_facts: List[EvidenceFact] = []

        # Find Title Block region (usually bottom-right or header/perimeter)
        title_block_candidates = []
        for tb in text_blocks:
            t_txt = tb.text.strip()
            b = tb.bbox
            is_bottom_or_right = (b.y2 > height * 0.5) or (b.x2 > width * 0.5) or (b.y1 < height * 0.25)
            if is_bottom_or_right:
                title_block_candidates.append(tb)

        # Scored matching against controlled vocabulary
        type_patterns = [
            ("P&ID", [
                r"process\s+(?:and|&)\s+instrumentation\s+diagram",
                r"piping\s+(?:and|&)\s+instrumentation\s+diagram",
                r"\bp[&/]?id\b",
                r"p\s*&\s*id"
            ], 0.98),
            ("Piping Isometric", [
                r"piping\s+isometric(?:\s+drawing)?",
                r"\bisometric\s+drawing\b"
            ], 0.95),
            ("General Arrangement", [
                r"general\s+arrangement(?:\s+drawing)?",
                r"\bga\s+drawing\b"
            ], 0.95),
            ("Plot Plan / Site Layout", [
                r"plot\s+plan",
                r"site\s+layout",
                r"overall\s+plot\s+plan"
            ], 0.95),
            ("Piping Layout", [
                r"piping\s+layout(?:\s+plan)?",
                r"piping\s+plan"
            ], 0.92),
            ("Equipment Layout", [
                r"equipment\s+layout"
            ], 0.92),
            ("Pipe Support Detail", [
                r"pipe\s+support\s+detail",
                r"pipe\s+support"
            ], 0.92),
            ("Instrumentation Layout", [
                r"instrumentation\s+layout"
            ], 0.92),
            ("Foundation Drawing", [
                r"foundation\s+drawing",
                r"foundation\s+details"
            ], 0.92),
            ("Revision / Title Block", [
                r"revision\s+(?:block|history)",
                r"title\s+block"
            ], 0.90),
        ]

        best_score = 0.0
        best_type = "Unknown"
        best_tb = None

        # Check title block candidates first
        candidates_to_check = title_block_candidates if title_block_candidates else text_blocks
        for tb in candidates_to_check:
            txt_lower = tb.text.strip().lower()
            for dtype, patterns, base_conf in type_patterns:
                for pat in patterns:
                    if re.search(pat, txt_lower, re.IGNORECASE):
                        # Weight higher if in prominent title block region
                        score = base_conf + (0.04 if tb in title_block_candidates else 0.0)
                        if score > best_score:
                            best_score = score
                            best_type = dtype
                            best_tb = tb

        if best_score > 0.6:
            doc_type = best_type
            conf = min(0.99, best_score)
            evidence_info = {
                "matched_text": best_tb.text if best_tb else "",
                "bbox": best_tb.bbox.to_list() if best_tb else []
            }
            metadata_facts.append(EvidenceFact(
                fact=f"Drawing type identified as {doc_type}",
                source="ocr",
                confidence=conf,
                source_region=best_tb.bbox.to_list() if best_tb else [],
                evidence_text=best_tb.text if best_tb else "",
                status="ENGINEERING_FACT"
            ))

        # Extract Unit, Project, Title, Drawing Number
        for tb in text_blocks:
            txt = tb.text.strip()
            
            # Unit number
            m_unit = re.search(r"(?:unit\s*[:\-\s]\s*|process\s+unit\s*[:\-\s]?\s*)([0-9]{3}[A-Z]?)", txt, re.IGNORECASE)
            if m_unit and not unit_no:
                unit_no = m_unit.group(1).upper()
                metadata_facts.append(EvidenceFact(
                    fact=f"Unit Number: {unit_no}",
                    source="ocr",
                    confidence=0.95,
                    source_region=tb.bbox.to_list(),
                    evidence_text=txt,
                    status="ENGINEERING_FACT"
                ))

            # System / Subject Title
            m_sys = re.search(r"(?:fuel\s+oil\s+transfer\s+system|amine\s+regeneration|sulfur\s+recovery|high\s+pressure\s+separator|column\s+overhead)", txt, re.IGNORECASE)
            if m_sys and not system_name:
                system_name = m_sys.group(0).upper()

            # Drawing Number
            m_dwg = re.search(r"(?:dwg\s*(?:no\.?|#)?\s*[:\.]?\s*|drawing\s*(?:no\.?|#)?\s*[:\.]?\s*)([0-9A-Z\-\_]{5,})", txt, re.IGNORECASE)
            if m_dwg and not drawing_no:
                drawing_no = m_dwg.group(1).strip()
                metadata_facts.append(EvidenceFact(
                    fact=f"Drawing Number: {drawing_no}",
                    source="ocr",
                    confidence=0.96,
                    source_region=tb.bbox.to_list(),
                    evidence_text=txt,
                    status="ENGINEERING_FACT"
                ))

            # Project Title
            if re.search(r"(?:project|terminal\s+project)", txt, re.IGNORECASE):
                project_name = txt

        # Fallback title selection
        title = system_name or title or Path(image_path).stem.replace("_", " ").title()

        return DocumentMetadata(
            document_type=doc_type,
            drawing_number=drawing_no,
            title=title,
            unit_number=unit_no,
            project_name=project_name,
            system_name=system_name,
            revision="0",
            source_file=image_path,
            original_width=width,
            original_height=height,
            classification_confidence=conf,
            classification_evidence=evidence_info
        ), metadata_facts

    def _extract_dimensions(
        self,
        text_blocks: List[TextObservation],
        lines: List[LineSegmentObservation],
        image_path: str
    ) -> Tuple[List[DimensionObservation], List[EvidenceFact]]:
        """Identifies dimensional annotations with numerical values and units."""
        dim_regex = re.compile(r"^\s*([ØøR]?\s*\d+(?:\.\d+)?)\s*(mm|m|cm|in|\"|'|ft|°|deg|kpa|bar|psi|m³|m3)?\s*$", re.IGNORECASE)
        dimensions: List[DimensionObservation] = []
        dim_facts: List[EvidenceFact] = []
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
                dim_id = f"dim_{counter:04d}"
                dimensions.append(DimensionObservation(
                    id=dim_id,
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
                dim_facts.append(EvidenceFact(
                    fact=f"Dimension / Measurement: {tb.text.strip()}",
                    source="ocr",
                    confidence=0.90,
                    source_region=tb.bbox.to_list(),
                    evidence_text=tb.text.strip(),
                    status="ENGINEERING_FACT"
                ))
        return dimensions, dim_facts

    def _fuse_entity_labels(
        self,
        entities: List[EngineeringEntity],
        text_blocks: List[TextObservation],
        image_path: str
    ) -> Tuple[List[EngineeringEntity], List[EvidenceFact]]:
        """Binds alphanumeric tag labels and measurements to discrete engineering entities with strict separation."""
        fused_entities: List[EngineeringEntity] = list(entities)
        entity_facts: List[EvidenceFact] = []

        # Known industrial tag patterns:
        # e.g. T-101, P-101 A/B, E-101, PSV-101, XV-101, LV-101, CV-101, FV-101, LT-101, PI-101, TI-101, TV-101, TR-101
        tag_pattern = re.compile(
            r"\b([A-Z]{1,4}\s*-\s*[0-9]{2,4}(?:\s*[A-Z](?:/[A-Z])?)?)\b",
            re.IGNORECASE
        )

        detected_tags: Dict[str, TextObservation] = {}
        for tb in text_blocks:
            clean = tb.text.strip()
            m = tag_pattern.search(clean)
            if m:
                norm_tag = re.sub(r"\s+", "", m.group(1).upper())
                # Normalize P-101A/B spacing
                norm_tag = re.sub(r"-", "-", norm_tag)
                if norm_tag not in detected_tags:
                    detected_tags[norm_tag] = tb

        # 1. Bind detected tags to closest symbol entities
        bound_tb_ids = set()
        for ent in fused_entities:
            if ent.label:
                continue

            ec = ent.bbox.center
            best_tag = None
            best_tb = None
            min_dist = float("inf")

            for tag, tb in detected_tags.items():
                tc = tb.bbox.center
                dist = math.hypot(tc.x - ec.x, tc.y - ec.y)
                if dist < 85.0 and dist < min_dist:
                    min_dist = dist
                    best_tag = tag
                    best_tb = tb

            if best_tag and best_tb:
                ent.label = best_tag
                ent.attributes["tag"] = best_tag
                ent.attributes["label_binding_distance_px"] = round(min_dist, 2)
                bound_tb_ids.add(best_tb.id)

        # 2. For tags found in OCR that didn't bind to a detected symbol box, create discrete entity nodes
        # This guarantees visible entities (like E-101, PSV-101, valves) are never dropped
        existing_labels = {e.label for e in fused_entities if e.label}
        new_ent_idx = len(fused_entities)
        for tag, tb in detected_tags.items():
            if tag not in existing_labels:
                new_ent_idx += 1
                # Infer entity class from prefix
                pfx = tag.split("-")[0].upper()
                if pfx in ("UNIT", "AREA", "DWG", "PAGE"):
                    continue

                eclass = "equipment"
                if pfx.startswith("PSV"):
                    eclass = "pressure_safety_valve"
                elif pfx.startswith(("XV", "LV", "CV", "FV", "TV", "BDV", "MOV", "SDV")):
                    eclass = "valve"
                elif pfx.startswith(("LT", "PI", "TI", "TR", "FT", "PT", "TT", "AT", "TE", "FE")):
                    eclass = "instrument"
                elif pfx.startswith("E") or pfx.startswith("HEX"):
                    eclass = "heat_exchanger"
                elif pfx.startswith("T") and not pfx.startswith(("TI", "TR", "TV", "TT")):
                    eclass = "tank"
                elif pfx.startswith("P") and not pfx.startswith(("PSV", "PI", "PT", "PG", "PDT", "PCV")):
                    eclass = "pump"
                elif pfx.startswith("V") and not pfx.startswith(("VALVE",)):
                    eclass = "vessel"

                discrete_ent = EngineeringEntity(
                    id=f"ent_{new_ent_idx:04d}",
                    entity_class=eclass,
                    label=tag,
                    bbox=tb.bbox,
                    confidence=0.92,
                    attributes={"tag": tag, "created_from_ocr_tag": True},
                    source=ProvenanceSource(
                        stage="fusion",
                        model_name="TagEntitySynthesizer",
                        image_path=image_path,
                        global_coordinates=tb.bbox.to_list()
                    )
                )
                fused_entities.append(discrete_ent)
                existing_labels.add(tag)

        # 3. Associate specifications and measurements to parent entities
        # e.g. "50 m³" -> T-101, "SET @ 10 bar(g)" -> PSV-101
        for ent in fused_entities:
            ec = ent.bbox.center
            e_label = ent.label or ent.id

            # Capacity binding for tanks / vessels
            if ent.entity_class in ("tank", "vessel") or (ent.label and ent.label.startswith("T-")):
                for tb in text_blocks:
                    m_cap = re.search(r"(\d+(?:\.\d+)?\s*(?:m³|m3|cubic\s*m|kl|bbl|liters))", tb.text, re.IGNORECASE)
                    if m_cap:
                        dist = math.hypot(tb.bbox.center.x - ec.x, tb.bbox.center.y - ec.y)
                        if dist < 160.0:
                            cap_val = m_cap.group(1).strip()
                            ent.attributes["capacity"] = cap_val
                            entity_facts.append(EvidenceFact(
                                fact=f"{e_label} capacity: {cap_val}",
                                source="ocr",
                                confidence=0.94,
                                source_region=tb.bbox.to_list(),
                                evidence_text=tb.text.strip(),
                                status="ENGINEERING_FACT",
                                target_entity_id=ent.id
                            ))
                            break

            # Set pressure binding for PSV
            if ent.entity_class == "pressure_safety_valve" or (ent.label and "PSV" in ent.label.upper()):
                for tb in text_blocks:
                    m_psv = re.search(r"(?:set\s*@\s*|set\s*[:\-\s]?\s*)?(\d+(?:\.\d+)?\s*(?:bar\(g\)|bar|kg/cm²|kg/cm2|psi|kpa))", tb.text, re.IGNORECASE)
                    if m_psv:
                        dist = math.hypot(tb.bbox.center.x - ec.x, tb.bbox.center.y - ec.y)
                        if dist < 120.0:
                            press_val = m_psv.group(1).strip()
                            ent.attributes["set_pressure"] = press_val
                            entity_facts.append(EvidenceFact(
                                fact=f"{e_label} set pressure: {press_val}",
                                source="ocr",
                                confidence=0.95,
                                source_region=tb.bbox.to_list(),
                                evidence_text=tb.text.strip(),
                                status="ENGINEERING_FACT",
                                target_entity_id=ent.id
                            ))
                            break

            # General entity fact
            ent_type_str = ent.entity_class.replace("_", " ")
            entity_facts.append(EvidenceFact(
                fact=f"Entity {e_label} ({ent_type_str}) identified",
                source="cv" if ent.source.stage == "cv_detector" else "fusion",
                confidence=ent.confidence,
                source_region=ent.bbox.to_list(),
                evidence_text=ent.label or ent.entity_class,
                status="ENGINEERING_FACT",
                target_entity_id=ent.id
            ))

        return fused_entities, entity_facts

